import csv
import ffmpeg
import librosa
import numpy as np
import soundfile as sf
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
def extract_audio(input_video, output_audio):
    """Create an FFmpeg command to extract raw audio from ``input_video``."""

    return (
        ffmpeg.input(str(input_video))
        .output(str(output_audio), acodec="pcm_s16le")
        .overwrite_output()
    )



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
    """Create an FFmpeg command that mixes two audio files into ``video_file``."""

    video = ffmpeg.input(str(video_file))
    a1 = ffmpeg.input(str(audio_file_1))
    a2 = ffmpeg.input(str(audio_file_2))

    mixed = ffmpeg.filter([a1, a2], "amix", inputs=2, duration="first")

    return (
        ffmpeg.output(
            video.video,
            mixed,
            str(output_video),
            vcodec="copy",
            acodec="aac",
            audio_bitrate="320k",
            ar=44100,
        ).overwrite_output()
    )


def run(command):
    """Execute a prepared FFmpeg command."""

    try:
        ffmpeg.run(command)
        print("FFmpeg command executed successfully.")
    except ffmpeg.Error as e:
        print("An error occurred while running FFmpeg:")
        if e.stderr:
            print(e.stderr.decode())
