import os
import csv
import random
import sys
import soundfile as sf
import torch
import tqdm
from cached_path import cached_path
from pathlib import Path
from omegaconf import OmegaConf
from importlib.resources import files
from hydra.utils import get_class
import librosa
from . import stt
import re
from . import subtitle_csv
import difflib


from f5_tts.infer.utils_infer import (
    hop_length,
    infer_process,
    load_model,
    load_vocoder,
    preprocess_ref_audio_text,
    # remove_silence_edges,
    # save_spectrogram,
    target_sample_rate,
)
from f5_tts.model import DiT, UNetT
from f5_tts.model.utils import seed_everything


class F5TTS:
    DEFAULT_MODELS = {
        "en": {
            "ckpt_file": "hf://SWivid/F5-TTS/F5TTS_v1_Base/model_1250000.safetensors",
            "vocab_file": "",
        },
        "es": {
            "ckpt_file": "hf://jpgallegoar/F5-Spanish/F5TTS_v1_Base/model_1200000.safetensors",
            "vocab_file": "",
        },
    }

    def __init__(self, model_type="F5-TTS", language="en", ckpt_file="", vocab_file="", ode_method="euler",
                 use_ema=True, vocoder_name="vocos", local_path=None, device=None):
        self.final_wave = None
        self.target_sample_rate = target_sample_rate
        self.hop_length = hop_length
        self.seed = -1
        self.mel_spec_type = vocoder_name
        self.language = language.lower()
        self.device = device or (
            "cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu"
        )
        print(f"device = {self.device}")

        if not ckpt_file or not vocab_file:
            model_info = self.DEFAULT_MODELS.get(self.language, {})
            ckpt_file = ckpt_file or model_info.get("ckpt_file", "")
            vocab_file = vocab_file or model_info.get("vocab_file", "")

        if ckpt_file.startswith("hf://"):
            ckpt_file = str(cached_path(ckpt_file))
        if vocab_file and vocab_file.startswith("hf://"):
            vocab_file = str(cached_path(vocab_file))

        self.load_vocoder_model(vocoder_name, local_path)
        self.load_ema_model(model_type, ckpt_file, vocoder_name, vocab_file, ode_method, use_ema)
        self.stt_model = stt.create_model()

    def load_vocoder_model(self, vocoder_name, local_path):
        self.vocoder = load_vocoder(vocoder_name, local_path is not None, local_path, self.device)

    def load_ema_model(self, model_type, ckpt_file, mel_spec_type, vocab_file, ode_method, use_ema):
        # Use correct model name
        model = "F5TTS_v1_Base"
        print(f"Loading model: {model}")
        
        # Load model configuration
        path_to_config = str(files("f5_tts").joinpath(f"configs/{model}.yaml"))
        print(f"Loading model configuration from {path_to_config}") 
        model_cfg = OmegaConf.load(
            path_to_config            
        )
        model_cls = get_class(f"f5_tts.model.{model_cfg.model.backbone}")
        model_arc = model_cfg.model.arch
        
        # Set correct checkpoint path
        if not ckpt_file:
            if mel_spec_type == "vocos":
                model_info = self.DEFAULT_MODELS.get(self.language, {})
                default = model_info.get("ckpt_file")
                if default:
                    ckpt_file = str(cached_path(default))
            elif mel_spec_type == "bigvgan":
                ckpt_file = str(cached_path("hf://SWivid/F5-TTS/F5TTS_Base_bigvgan/model_1250000.pt"))
                print(f"Loading checkpoint from {ckpt_file} for bigvgan")
        
        # Load the model with correct parameters
        self.ema_model = load_model(
            model_cls, model_arc, ckpt_file, 
            mel_spec_type=mel_spec_type, 
            vocab_file=vocab_file, 
            device=self.device
        )

        # For older models
        if model_type == "F5-TTS":
            model_cfg = dict(dim=1024, depth=22, heads=16, ff_mult=2, text_dim=512, conv_layers=4)
            model_cls = DiT
            print(f"Loading model {model_type} with config {model_cfg}")
        elif model_type == "E2-TTS":
            if not ckpt_file:
                ckpt_file = str(cached_path("hf://SWivid/E2-TTS/E2TTS_Base/model_1200000.safetensors"))
                print(f"Loading checkpoint from {ckpt_file} for E2-TTS")
            model_cfg = dict(dim=1024, depth=24, heads=16, ff_mult=4)
            model_cls = UNetT
            print(f"Loading model {model_type} with config {model_cfg}")
        else:
            raise ValueError(f"Unknown model type: {model_type}")

        self.ema_model = load_model(
            model_cls, model_cfg, ckpt_file, mel_spec_type, vocab_file, ode_method, use_ema, self.device
        )

    def export_wav(self, wav, file_wave, remove_silence=None):
        sf.write(file_wave, wav, self.target_sample_rate)

    def infer(self, ref_file, ref_text, gen_text, show_info=print, progress=tqdm, target_rms=0.1,
              cross_fade_duration=0.15, sway_sampling_coef=-1, cfg_strength=2, nfe_step=32, speed=1.0,
              fix_duration=None, 
              remove_silence=True, # to start from start
              file_wave=None, seed=-1,
              remove_silence_top_db=35):
        if seed == -1:
            seed = random.randint(0, sys.maxsize)
        seed_everything(seed)
        self.seed = seed

        ref_file, ref_text = preprocess_ref_audio_text(ref_file, ref_text)#, device=self.device)

        wav, sr, spect = infer_process(
            ref_file,
            ref_text,
            gen_text,
            self.ema_model,
            self.vocoder,
            self.mel_spec_type,
            show_info=show_info,
            progress=progress,
            target_rms=target_rms,
            cross_fade_duration=cross_fade_duration,
            nfe_step=nfe_step,
            cfg_strength=cfg_strength,
            sway_sampling_coef=sway_sampling_coef,
            speed=speed,
            fix_duration=fix_duration,
            device=self.device,
        )

        if remove_silence:
            trimmed, index = librosa.effects.trim(wav, top_db=remove_silence_top_db)
            print(f"Trimmed from {file_wave} from sample {index[0]} to {index[1]}")
            wav = trimmed
            

        if file_wave is not None:
            self.export_wav(wav, file_wave, remove_silence)

        return wav, sr

    @staticmethod
    def all_segments_in_folder_check(csv_file:str, folder:str):
        """
        Checks if all fragments specified in the CSV file are present in the given folder.

        Args:
            csv_file (str): Path to the CSV file containing the fragment details.
            folder (str): Path to the folder where the fragments should be located.
        """
        with open(csv_file, 'r', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            missing_files = []
            for i, _ in enumerate(reader):
                expected_file = f"segment_{i + 1}.wav"
                if not os.path.exists(os.path.join(folder, expected_file)):
                    missing_files.append(expected_file)

        if not missing_files:
            print("All fragments are present in the folder.")
            return True
        else:
            print(f"Missing fragments: {len(missing_files)} missing files.")
            for missing_file in missing_files:
                print(f"Missing file: {missing_file}")
            return False

    @staticmethod
    def linear_predict(speed_1, duration_1, speed_2, duration_2, limit_duration):
        """
        Performs linear extrapolation to predict the speed that would result in the desired duration.

        Args:
            speed_1 (float): The first speed value.
            duration_1 (float): The duration corresponding to the first speed value.
            speed_2 (float): The second speed value.
            duration_2 (float): The duration corresponding to the second speed value.
            limit_duration (float): The target duration for which we want to predict the speed.

        Returns:
            float: The predicted speed value that should result in the target duration.
        """
        if duration_1 == duration_2:
            return speed_1  # If durations are equal, return the first speed (arbitrary choice)

        # Linear extrapolation formula: speed = speed_1 + (limit_duration - duration_1) * (speed_2 - speed_1) / (duration_2 - duration_1)
        predicted_speed = speed_1 + (limit_duration - duration_1) * (speed_2 - speed_1) / (duration_2 - duration_1)
        return predicted_speed

    def infer_wav(self, gen_text, speed, ref_file, ref_text, file_wave=None):
        wav, sr = self.infer(
            ref_file=ref_file,
            ref_text=ref_text,
            gen_text=gen_text,
            speed=speed,
            show_info=print,
            progress=tqdm,
            fix_duration=None,
            file_wave=file_wave
        )
        return wav, sr, len(wav) / sr 

    def generate_wav_if_longer(self, wav, sr, gen_text, duration, previous_duration, previous_speed, 
                                ref_file, ref_text, i, 
                                counter_max=10):
        counter = 0
        start_speed = previous_speed + 0.1
        while duration < previous_duration:  
            print(f"duration < duration_seconds_tts = {duration} < {previous_duration}")
            next_speed = previous_speed + 0.1
            wav, sr,next_duration = self.infer_wav(gen_text, next_speed, ref_file, ref_text)

            predict_linear_speed = self.linear_predict(previous_speed, previous_duration, next_speed, next_duration, duration)
            if predict_linear_speed-previous_speed > 0.1:  # if jump is less then 0.1 speed make speed just +0.1speed
                next_speed = predict_linear_speed
                print(f"Let`s regenerate {i}-fragment with speed = {next_speed}")
                wav, sr = self.infer(
                    ref_file=ref_file,
                    ref_text=ref_text,
                    gen_text=gen_text,
                    speed=next_speed,
                    fix_duration=None,
                    # file_wave=f"segment_{i}_speed_{next_speed}.wav" # for debug
                )
            previous_duration = len(wav) / sr
            previous_speed = next_speed
            counter += 1
            if counter > counter_max:
                wav, sr,previous_duration = self.infer_wav(gen_text, start_speed, ref_file, ref_text)
                break
        return wav, sr, previous_duration

    def clean_text(self,text,replacement = r"[.,!?\-:;’'\"]"):
        text = text.strip().lower().replace("\n", " ")
        text = re.sub(replacement, " ", text)
        text = re.sub(r"\s+", " ", text)  # collapse multiple spaces
        return text.strip()   

    def similarity(self,gen_text,subtitles_text):
        return difflib.SequenceMatcher(None, gen_text, subtitles_text).ratio()


    def is_generated_text_equal_to_subtitles_text(self,wav,sr,subtitles_text):
        gen_text = stt.wav2txt(self.stt_model, wav, sr)
        gen_text = self.clean_text(gen_text)
        subtitles_text = self.clean_text(subtitles_text)
        similarity = self.similarity(gen_text,subtitles_text)
        if gen_text != subtitles_text:
            print(f"ALARM !!! Generated text: {gen_text} != Subtitles text: {subtitles_text} \n Similarity: {similarity}")
        return gen_text == subtitles_text,gen_text,subtitles_text,similarity 

    def _get_speaker_config(self, row, speakers, default_speaker):
        """Get speaker configuration for the given row."""
        try:
            speaker_name = row.get('Speaker', '')
            if speaker_name and speaker_name in speakers:
                return speakers[speaker_name]["ref_text"], speakers[speaker_name]["ref_file"]
            raise KeyError(f"Speaker '{speaker_name}' not found")
        except Exception as e:
            print(f"Using default speaker: {str(e)}")
            return default_speaker["ref_text"], default_speaker["ref_file"]

    def _generate_audio_segment(self, gen_text, duration, ref_text, ref_file, previous_speed, i):
        """Generate audio segment for the given text and configuration."""
        try:
            wav, sr, _ = self.infer_wav(gen_text, previous_speed, ref_file, ref_text)
            wav, sr, _ = self.generate_wav_if_longer(
                wav, sr, gen_text, duration, len(wav)/sr, previous_speed, 
                ref_file, ref_text, i
            )
            return wav, sr, None
        except Exception as e:
            return None, None, str(e)

    def _save_audio_segments(self, generated_segments):
        """Save all generated audio segments to files."""
        for wav, file_wave, sr in generated_segments:
            try:
                sf.write(file_wave, wav, sr)
                print(f"Saved WAV as {file_wave}")
            except Exception as e:
                print(f"Error saving {file_wave}: {str(e)}")

    def _generate_excel_report(self, csv_file, filename_errors_csv):
        """Generate Excel report from the error CSV file."""
        excel_file_name = os.path.basename(filename_errors_csv)
        excel_file_name = excel_file_name.split("_3.0_")[0] + ".xlsx"
        parent_of_parent = os.path.dirname(os.path.dirname(filename_errors_csv))
        excel_file = os.path.join(parent_of_parent, excel_file_name)
        subtitle_csv.csv2excel(filename_errors_csv, excel_file)
        return excel_file

    def _process_row(self, row, i, output_folder, speakers, default_speaker, rewrite, writer):
        """Process a single row from the CSV file."""
        file_wave = os.path.join(output_folder, f"segment_{i + 1}.wav")
        if not rewrite and os.path.exists(file_wave):
            print(f"Skipping existing file: {file_wave}")
            return None
            
        duration = float(row.get('Duration', 0))
        gen_text = row.get('Text', '').strip()
        if not gen_text:
            print(f"Skipping empty text at row {i+1}")
            return None
            
        previous_speed = float(row.get('TTS Speed Closest', 1.0))
        ref_text, ref_file = self._get_speaker_config(row, speakers, default_speaker)

        # Generate audio
        wav, sr, error = self._generate_audio_segment(
            gen_text, duration, ref_text, ref_file, previous_speed, i
        )
        
        if error:
            print(f"Error processing row {i+1}: {error}")
            writer.writerow({
                **row,
                "similarity": "0.00",
                "gen_error": "1",
                "whisper_text": "",
                "subtitle_text": f"Error: {error}"
            })
            return None

        print(f"Generated WAV-{i+1} with duration {len(wav)/sr:.2f}s")
        
        # Verify the generated audio
        is_equal, gen_text_clean, subtitles_text, similarity = self.is_generated_text_equal_to_subtitles_text(
            wav, sr, gen_text
        )
        
        # Write results
        writer.writerow({
            **row,
            "similarity": f"{similarity:.2f}",
            "gen_error": "1" if not is_equal else "0",
            "whisper_text": gen_text_clean,
            "subtitle_text": subtitles_text
        })
        
        return wav, file_wave, sr

    def generate_from_csv_with_speakers(self, csv_file, output_folder, speakers, default_speaker, rewrite=False):
        """
        Generate audio segments from a CSV file with speaker configurations.
        
        Args:
            csv_file: Path to input CSV file
            output_folder: Directory to save generated audio files
            speakers: Dictionary mapping speaker names to their configurations
            default_speaker: Default speaker configuration to use when speaker not found
            rewrite: If True, overwrite existing files
        """
        os.makedirs(output_folder, exist_ok=True)
        filename_errors_csv = f"{str(csv_file)[:-4]}_errors.csv"
        
        # Read and validate input
        try:
            with open(csv_file, 'r', encoding='utf-8') as csvfile:
                rows = list(csv.DictReader(csvfile))
        except Exception as e:
            print(f"Error reading CSV file: {str(e)}")
            return
            
        if not rows:
            print("No rows found in CSV file")
            return
        
        generated_segments = []
        
        # Process each row and write results to CSV
        with open(filename_errors_csv, 'w', newline='', encoding='utf-8') as csv_writer:
            fieldnames = rows[0].keys() if rows else []
            writer_filednames = [*fieldnames, "similarity", "gen_error", "whisper_text", "subtitle_text"]
            writer = csv.DictWriter(csv_writer, fieldnames=writer_filednames, delimiter=';')
            writer.writeheader()
            
            for i, row in enumerate(rows):
                result = self._process_row(
                    row, i, output_folder, speakers, default_speaker, rewrite, writer
                )
                if result:
                    generated_segments.append(result)
        
        # Save all audio segments
        self._save_audio_segments(generated_segments)
        
        # Generate Excel report
        try:
            excel_file = self._generate_excel_report(csv_file, filename_errors_csv)
            print(f"Excel report generated: {excel_file}")
        except Exception as e:
            print(f"Error generating Excel report: {str(e)}")
        
        print(f"Processing complete. Generated {len(generated_segments)} audio segments in {output_folder}")
        return filename_errors_csv



    def generate_speeds_csv(self, output_csv, ref_text, ref_file):
        gen_text = "Some call me nature, others call me mother nature. Let's try some long text. We are just trying to get more fidelity. It's OK!"
        speeds = [0.3,0.4,0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 1.9, 2.0, 2.1, 2.2, 2.3, 2.4, 2.5]
        rows = []
        Path(output_csv).parent.mkdir(parents=True, exist_ok=True)
        for speed in speeds:

            file_name = Path(output_csv).parent/f"gen_out_{speed}.wav"


            wav, sr = self.infer(ref_file, ref_text, gen_text, speed=speed,fix_duration=None, remove_silence=True,  file_wave=file_name)
            duration = len(wav) / sr
            symbol_duration = duration / len(gen_text)  # Assuming each character is considered a symbol

            rows.append([speed, duration, symbol_duration, file_name])

        with open(output_csv, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(['speed', 'duration', 'symbol_duration', 'file_name'])
            writer.writerows(rows)
        print(f"CSV file generated and saved as {output_csv}")

