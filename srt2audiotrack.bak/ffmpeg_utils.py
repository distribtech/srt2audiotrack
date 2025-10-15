import csv
import ffmpeg


# Read CSV file to get volume reduction time intervals
def parse_volume_intervals(csv_file) -> list[tuple[str, str]]:
    with open(csv_file, 'r', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        return [(row['Start Time'], row['End Time']) for row in reader]

def extract_audio(input_video, output_audio, target_lufs=-16.0, target_peak=-1.0):
    """Extract and normalize audio from video file.
    
    Args:
        input_video: Path to input video file
        output_audio: Path to save output audio file
        target_lufs: Target loudness in LUFS (default: -16.0, typical for streaming)
        target_peak: True peak value in dB (default: -1.0)
    """
    (
        ffmpeg
        .input(str(input_video))
        .audio
        .filter('loudnorm',
                i=target_lufs,
                tp=target_peak)
        .output(str(output_audio),
                acodec='pcm_s16le',
                # ar='44100',  # Standard CD quality sample rate
                # ac=2 # Stereo audio
                )      
        .overwrite_output()
        .run()
    )

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

def create_ffmpeg_mix_video(video_file, audio_file_1, audio_file_2, output_video):
    """Create an FFmpeg command that mixes two audio files into ``video_file``."""

    video = ffmpeg.input(str(video_file))
    a1 = ffmpeg.input(str(audio_file_1))
    a2 = ffmpeg.input(str(audio_file_2))

    mixed = ffmpeg.filter([a1, a2], "amix", inputs=2, duration="first")

    run (
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
