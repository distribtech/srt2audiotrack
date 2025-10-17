import csv
import os
from pathlib import Path
import soundfile as sf
import numpy as np
from .sync_utils import time_to_seconds
import librosa
import demucs.separate
import shutil
import librosa

def prepare_and_normalize_accompaniment(acomponiment_temp: Path,
                                        acomponiment_temp_stereo: Path,
                                        acomponiment: Path,
                                        sample_rate: int,
                                        subtype: str = 'PCM_16'):
    """
    Read demucs output, resample to sample_rate, ensure stereo and normalize.
    Returns path to final accompaniment file (acomponiment).
    """
    # read with soundfile to keep float32 and channel count intact
    data, sr_in = sf.read(str(acomponiment_temp), dtype='float32', always_2d=True)  # (frames, channels)
    channels = data.shape[1]

    # resample per-channel if needed
    if sr_in != sample_rate:
        resampled_ch = []
        for ch in range(channels):
            resampled_ch.append(librosa.resample(data[:, ch], orig_sr=sr_in, target_sr=sample_rate))
        # stack channels => (channels, frames) then transpose to (frames, channels)
        resampled = np.vstack(resampled_ch).T
        sr_out = sample_rate
    else:
        resampled = data
        sr_out = sr_in

    # write a resampled temp file (don't overwrite demucs original)
    temp_resampled = acomp = Path(acomponiment_temp).with_name(f"{acomponiment_temp.stem}_resampled.wav")
    sf.write(str(temp_resampled), resampled, sr_out, subtype=subtype)

    # ensure stereo: if mono duplicate channel, if >2 keep first two
    if resampled.shape[1] == 1:
        convert_mono_to_stereo(str(temp_resampled), str(acomponiment_temp_stereo))
    else:
        if resampled.shape[1] > 2:
            res_stereo = resampled[:, :2]
        else:
            res_stereo = resampled
        sf.write(str(acomponiment_temp_stereo), res_stereo, sr_out, subtype=subtype)

    # normalize the stereo file (uses existing normalize_stereo_audio implementation)
    normalize_stereo_audio(str(acomponiment_temp_stereo), str(acomponiment))


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
    demucs.separate.main(["--jobs", "4","-o", str(directory), "--two-stems", "vocals", "-n", model_demucs, str(out_ukr_wav)])
    
    if acomponiment_temp.exists():
            prepare_and_normalize_accompaniment(acomponiment_temp,
                                        acomponiment_temp_stereo,
                                        acomponiment,
                                        sample_rate,
                                        subtype = 'PCM_16')
            # Load and normalize the audio
            # y, sr = librosa.load(acomponiment_temp, sr=44100)  # load with 44.1k
            # y_16k = librosa.resample(y, orig_sr=44100, target_sr=sample_rate)
            # sf.write(acomponiment_temp, y_16k, sample_rate)
            # convert_mono_to_stereo(acomponiment_temp, acomponiment_temp_stereo)
            # normalize_stereo_audio(acomponiment_temp_stereo, acomponiment)
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
    if audio.ndim == 1:
        # Duplicate mono channel to create stereo
        stereo_audio = np.vstack([audio, audio])
    else:
        print("The input file is not mono. Just copying to {output_path}.")

    # Save as stereo WAV
    sf.write(output_path, stereo_audio.T, sr)

    print(f"Converted {input_path} to stereo and saved as {output_path}")


def normalize_stereo_audio(input_path: str, output_path: str, target_db: float = -18.0, max_gain_db: float = 0.0, subtype: str = 'PCM_16'):
    """
    Normalize stereo audio per channel to target_db (dBFS).
    Prevents positive boosting above max_gain_db (default 0 dB) and avoids clipping by peak-limiting.
    """
    # read with soundfile to preserve exact shape/dtype: returns (frames, channels)
    audio, sr = sf.read(input_path, dtype='float32', always_2d=True)
    if audio.ndim == 1 or audio.shape[1] < 2:
        raise ValueError("The input file is mono. Use a mono-specific normalization function.")

    # transpose to (channels, samples)
    audio_ch = audio.T.astype(np.float64)

    eps = 1e-12
    # per-channel RMS
    rms = np.sqrt(np.mean(audio_ch**2, axis=1) + eps)
    rms_db = 20.0 * np.log10(rms + eps)

    # desired gain per channel, but do not allow boosting above max_gain_db
    gain_db = target_db - rms_db
    gain_db = np.minimum(gain_db, max_gain_db)
    gain = 10.0 ** (gain_db / 20.0)

    # apply per-channel gain
    normalized = audio_ch * gain[:, None]

    # peak limiting: if any sample exceeds 1.0, scale down slightly below 1.0 to avoid clipping on integer write
    peak = np.max(np.abs(normalized))
    if peak > 1.0:
        scale = 0.999 / peak
        normalized *= scale

    # final safety clip
    normalized = np.clip(normalized, -1.0, 1.0)

    # write back as (frames, channels) with explicit subtype
    sf.write(output_path, normalized.T.astype(np.float32), sr, subtype=subtype)
    print(f"Normalized {input_path} to {target_db} dB per channel (max_gain_db={max_gain_db}) and saved as {output_path}")


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
        start_time, end_time = time_to_seconds(start_time), time_to_seconds(end_time)
        start_sample = int(librosa.time_to_samples(float(start_time), sr=sr))
        end_sample = int(librosa.time_to_samples(float(end_time), sr=sr))

        # Apply volume adjustment in the given range for both channels
        y[:, start_sample:end_sample] = \
             y[:, start_sample:end_sample] * (1 - acomponiment_coef - voice_coef) +\
             a[:, start_sample:end_sample]*acomponiment_coef + \
             original[:, start_sample:end_sample]*voice_coef

    # Save the modified audio
    sf.write(output_audio, y.T, sr)  # Transpose y to match the expected shape for stereo

    print(f"Stereo volume adjusted and saved to {output_audio}")
