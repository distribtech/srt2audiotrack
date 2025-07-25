import csv
import subprocess
import librosa
import soundfile as sf
import numpy as np
from sync_utils import time_to_seconds

# Read CSV file to get volume reduction time intervals
def parse_volume_intervals(csv_file):
    volume_intervals = []
    with open(csv_file, 'r', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        for row in reader:
            start_time = row['Start Time']
            end_time = row['End Time']
            volume_intervals.append((start_time, end_time))
    return volume_intervals

# Create the ffmpeg command to reduce volume in specified intervals
def extract_audio(input_video, output_audio):  #, volume_intervals, k_volume):
    ffmpeg_command = (
        f'ffmpeg -y -i "{input_video}" '
        f'-c:a pcm_s16le "{output_audio}"'
    )

    return ffmpeg_command



def adjust_stereo_volume_with_librosa(
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

    # Convert time to sample index
    for start_time, end_time in volume_intervals:
        start_time, end_time = time_to_seconds(start_time), time_to_seconds(end_time)
        start_sample = int(librosa.time_to_samples(float(start_time), sr=sr))
        end_sample = int(librosa.time_to_samples(float(end_time), sr=sr))

        # Apply volume adjustment in the given range for both channels
        y[:, start_sample:end_sample] =  y[:, start_sample:end_sample] * voice_coef + a[:, start_sample:end_sample]*(1-voice_coef)*acomponiment_coef

    # Save the modified audio
    sf.write(output_audio, y.T, sr)  # Transpose y to match the expected shape for stereo

    print(f"Stereo volume adjusted and saved to {output_audio}")


# Create the ffmpeg command to mix two audio files
def create_ffmpeg_mix_video_file_command(video_file, audio_file_1, audio_file_2, output_video):
    # Build the full ffmpeg command to mix two audio files
    # The `-shortest` flag ensures that the length is taken from the shortest input, i.e., the first audio file.
    ffmpeg_command = [
        "ffmpeg", "-y", "-i", f"\"{video_file}\"", "-i", f"\"{audio_file_1}\"", "-i", f"\"{audio_file_2}\"",
        " -filter_complex", "[1:a][2:a]amix=inputs=2:duration=first[aout]",
        "-map", "0:v", "-map", "[aout]", "-c:v", "copy", "-c:a", "aac", "-b:a", "320k", "-ar", "44100", f"\"{output_video}\""
    ]

    return " ".join(ffmpeg_command)


def run(command):
    try:
        # Run the command using subprocess
        result = subprocess.run(command, check=True) #, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print("FFmpeg command executed successfully.")
    except subprocess.CalledProcessError as e:
        print("An error occurred while running FFmpeg:")
