import csv
import os
import soundfile as sf
import numpy as np
from .sync_utils import time_to_seconds
import librosa
import shutil
import librosa

from .docker_models import run_demucs


def extract_acomponiment_or_vocals(directory, subtitle_name, out_ukr_wav,
        sample_rate,
        pipeline_suffix="_extracted.wav",
        model_demucs = "mdx_extra",
        sound_name="no_vocals.wav",
        subtype='PCM_16'  # Use 16-bit PCM
    ):
    acomponiment = directory / f"{subtitle_name}{pipeline_suffix}"    
    model_folder = directory / model_demucs
    demucs_folder = model_folder / out_ukr_wav.stem
    acomponiment_temp = demucs_folder / sound_name
    acomponiment_temp_stereo = directory / f"{subtitle_name}{pipeline_suffix}_stereo.wav"
    run_demucs(out_ukr_wav, directory, model=model_demucs)
    
    if acomponiment_temp.exists():
            # Load and normalize the audio
            y, sr = librosa.load(acomponiment_temp, sr=44100)  # load with 44.1k
            y_16k = librosa.resample(y, orig_sr=44100, target_sr=sample_rate)
            sf.write(acomponiment_temp, y_16k, sample_rate)
            convert_mono_to_stereo(acomponiment_temp, acomponiment_temp_stereo)
            normalize_stereo_audio(acomponiment_temp_stereo, acomponiment)
            # Clean up
            shutil.rmtree(model_folder)

    # Verify the accompaniment exists and is valid
    if not acomponiment.exists():
        raise FileNotFoundError(f"Failed to extract accompaniment: {acomponiment}")
    return acomponiment
        
    

def collect_full_audiotrack(fragments_folder, csv_file, output_audio_file):
    """Concatenate all audio segments in the specified order from csv_file into a full audio track, using start times to add silence."""
    audio_segments = []
    sample_rate = None

    with open(csv_file, 'r', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        previous_end_time = 0.0  # Start at 0 for initial silence

        for i, row in enumerate(reader):
            start_time_str = row.get('Start Time')

            if start_time_str is None:
                print(f"Warning: 'Start Time' missing in row {i + 1}. Skipping segment.")
                continue

            try:
                start_time = time_to_seconds(start_time_str)
            except ValueError as e:
                print(f"Error in row {i + 1}: {e}. Skipping segment.")
                continue

            segment_file = os.path.join(fragments_folder, f"segment_{i + 1}.wav")

            if os.path.exists(segment_file):
                wav, sr = sf.read(segment_file)

                # Ensure sample rate consistency
                if sample_rate is None:
                    sample_rate = sr
                elif sample_rate != sr:
                    raise ValueError(f"Sample rate mismatch in segment {segment_file}")

                # Calculate silence duration (in samples) needed before this segment
                if start_time > previous_end_time:
                    silence_duration = int((start_time - previous_end_time) * sample_rate)
                    silence = np.zeros(silence_duration)
                    audio_segments.append(silence)

                # Add the current segment
                audio_segments.append(wav)
                print(f"Processed start time: {start_time_str} - {previous_end_time/60}")
                # Update previous_end_time to reflect the end time of the current segment
                previous_end_time = start_time + len(wav) / sample_rate
            else:
                print(f"Warning: Expected segment {segment_file} not found.")

    # Concatenate all segments with silences
    if audio_segments:
        full_audio = np.concatenate(audio_segments)
        sf.write(output_audio_file, full_audio, sample_rate)
        print(f"Full audio track saved to {output_audio_file}")
    else:
        print("No audio segments to concatenate. Please check the input files.")

def convert_mono_to_stereo(input_path: str, output_path: str):
    # Load mono audio
    audio, sr = librosa.load(input_path, sr=None, mono=True)

    # Duplicate mono channel to create stereo
    stereo_audio = np.vstack([audio, audio])

    # Save as stereo WAV
    sf.write(output_path, stereo_audio.T, sr)

    print(f"Converted {input_path} to stereo and saved as {output_path}")


def normalize_stereo_audio(input_path: str, output_path: str, target_db: float = -18.0):
    audio, sr = librosa.load(input_path, sr=None, mono=False)

    if audio.ndim == 1:
        raise ValueError("The input file is mono. Use a mono-specific normalization function.")

    # Compute RMS loudness for each channel
    rms_left = np.sqrt(np.mean(audio[0]**2))
    rms_right = np.sqrt(np.mean(audio[1]**2))

    # Convert RMS to decibel scale
    rms_db_left = 20 * np.log10(rms_left)
    rms_db_right = 20 * np.log10(rms_right)

    # Compute gain needed for each channel
    gain_db_left = target_db - rms_db_left
    gain_db_right = target_db - rms_db_right

    gain_left = 10 ** (gain_db_left / 20)
    gain_right = 10 ** (gain_db_right / 20)

    # Apply gain to each channel separately
    normalized_audio = np.vstack([audio[0] * gain_left, audio[1] * gain_right])

    # Save the normalized stereo audio
    sf.write(output_path, normalized_audio.T, sr)

    print(f"Normalized {input_path} to {target_db} dB per channel and saved as {output_path}")

def adjust_stereo_volume_with_librosa(
        original_wav,
        input_audio,
        output_audio,
        volume_intervals,
        acomponiment,
        acomponiment_coef,
        voice_coef,
    ):
    """
    Adjusts the volume of a stereo audio file using librosa.

    :param input_audio: Path to input WAV file
    :param output_audio: Path to output WAV file
    :param volume_intervals: List of tuples (start_time, end_time) where volume needs adjustment
    :param acomponiment: Path to extracted accompaniment audio
    :param acomponiment_coef: Volume coefficient for the accompaniment track
    :param voice_coef: Volume coefficient for the original voice
    """
    # Load audio file with stereo channels
    y, sr = librosa.load(input_audio, sr=None, mono=False)
    a, sr = librosa.load(acomponiment, sr=None, mono=False)
    original, sr = librosa.load(original_wav, sr=None, mono=False)

    # Convert time to sample index
    for start_time, end_time in volume_intervals:
        start_sample = time2sample(start_time, sr)
        end_sample = time2sample(end_time, sr)

        # Apply volume adjustment in the given range for both channels
        y[:, start_sample:end_sample] = \
             y[:, start_sample:end_sample] * (1 - acomponiment_coef - voice_coef) +\
             a[:, start_sample:end_sample]*acomponiment_coef + \
             original[:, start_sample:end_sample]*voice_coef

    # Save the modified audio
    sf.write(output_audio, y.T, sr)  # Transpose y to match the expected shape for stereo

    print(f"Stereo volume adjusted and saved to {output_audio}")

def time2sample(time, sr):
    seconds = time_to_seconds(time) 
    return int(librosa.time_to_samples(float(seconds), sr=sr))
