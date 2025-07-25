import argparse
import os
from pathlib import Path


import srt2csv
import srt2audio
import correct_times
import wavs2wav
import ffmpeg_commands
import vocabular
from wavs2wav import convert_mono_to_stereo, normalize_stereo_audio
from srt2csv import get_speakers_from_folder, check_texts, check_speeds_csv
from vocabular import check_vocabular
from wavs2wav import extract_acomponiment_or_vocals


def modify_subtitles(subtitle, vocabular_pth):
    """Apply vocabulary corrections and return helper paths."""
    directory = subtitle.with_suffix("")
    directory.mkdir(exist_ok=True)
    subtitle_name = subtitle.stem
    out_path = directory / f"{subtitle_name}_0_mod.srt"

    if not out_path.exists():
        vocabular.modify_subtitles_with_vocabular_text_only(
            subtitle, vocabular_pth, out_path
        )

    return directory, subtitle_name, out_path


def convert_to_csv(directory, subtitle_name, out_path, speakers, default_speaker):
    """Convert subtitles to CSV and generate English audio."""
    srt_csv_file = directory / f"{subtitle_name}_1.0_srt.csv"
    if not srt_csv_file.exists():
        srt2csv.srt_to_csv(out_path, srt_csv_file)

    output_csv_with_speakers = directory / f"{subtitle_name}_1.5_output_speakers.csv"
    if not output_csv_with_speakers.exists():
        srt2csv.add_speaker_columns(srt_csv_file, output_csv_with_speakers)

    output_with_preview_speeds_csv = directory / f"{subtitle_name}_3.0_output_speed.csv"
    if not output_with_preview_speeds_csv.exists():
        srt2csv.add_speed_columns_with_speakers(
            output_csv_with_speakers, speakers, output_with_preview_speeds_csv
        )

    if not srt2audio.F5TTS.all_segments_in_folder_check(
        output_with_preview_speeds_csv, directory
    ):
        f5tts = srt2audio.F5TTS()
        f5tts.generate_from_csv_with_speakers(
            output_with_preview_speeds_csv,
            directory,
            speakers,
            default_speaker,
            rewrite=False,
        )

    corrected_time_output_speed_csv = (
        directory / f"{subtitle_name}_4_corrected_output_speed.csv"
    )
    if not corrected_time_output_speed_csv.exists():
        correct_times.correct_end_times_in_csv(
            directory, output_with_preview_speeds_csv, corrected_time_output_speed_csv
        )

    output_audio_file = directory / f"{subtitle_name}_5.0_output_audiotrack_eng.wav"
    if not output_audio_file.exists():
        wavs2wav.collect_full_audiotrack(
            directory, corrected_time_output_speed_csv, output_audio_file
        )

    stereo_eng_file = directory / f"{subtitle_name}_5.3_stereo_eng.wav"
    if not stereo_eng_file.exists():
        convert_mono_to_stereo(output_audio_file, stereo_eng_file)

    return srt_csv_file, stereo_eng_file


def handle_video(
    video_path, directory, subtitle_name, srt_csv_file, stereo_eng_file, coef
):
    """Process the input video and mix with generated audio."""
    if not os.path.exists(video_path):
        return

    out_ukr_wav = directory / f"{subtitle_name}_5.5_out_ukr.wav"
    if not out_ukr_wav.exists():
        command = ffmpeg_commands.extract_audio(video_path, out_ukr_wav)
        ffmpeg_commands.run(command)

    acomponiment = directory / f"{subtitle_name}_5.7_accompaniment_ukr.wav"
    if not acomponiment.exists():
        acomponiment_extracted = extract_acomponiment_or_vocals(
            directory, subtitle_name, out_ukr_wav
        )
        normalize_stereo_audio(acomponiment_extracted, acomponiment)
        os.remove(acomponiment_extracted)

    output_audio = directory / f"{subtitle_name}_6_out_reduced_ukr.wav"
    if not output_audio.exists():
        volume_intervals = ffmpeg_commands.parse_volume_intervals(srt_csv_file)
        normalize_stereo_audio(out_ukr_wav, out_ukr_wav)
        ffmpeg_commands.adjust_stereo_volume_with_librosa(
            out_ukr_wav, output_audio, volume_intervals, coef, acomponiment
        )

    ext = Path(video_path).suffix.lower()
    match ext:
        case ".mp4" | ".mkv" | ".avi":
            mix_video = directory.parent / f"{subtitle_name}_out_mix{ext}"
        case _:
            print(f"Unsupported video format: {video_path}")
            return

    if not mix_video.exists():
        command = ffmpeg_commands.create_ffmpeg_mix_video_file_command(
            video_path, output_audio, stereo_eng_file, mix_video
        )
        ffmpeg_commands.run(command)


def make_video_from(video_path, subtitle, speakers, default_speaker, vocabular_pth, coef):
    directory, subtitle_name, out_path = modify_subtitles(subtitle, vocabular_pth)
    srt_csv_file, stereo_eng_file = convert_to_csv(
        directory, subtitle_name, out_path, speakers, default_speaker
    )
    handle_video(
        video_path, directory, subtitle_name, srt_csv_file, stereo_eng_file, coef
    )

def fast_rglob(root_dir, extension, exclude_ext): # for network drives
    ext = extension.lstrip('.')
    sbt_files = []
    for dirpath, _, filenames in os.walk(root_dir):
        # print(dirpath,dirnames,filenames)
        for file in filenames:
            if file.endswith(f".{ext}") and not file.endswith(exclude_ext):
                sbt_files.append(os.path.join(dirpath, file))
    return sbt_files



def main():
    # Initialize the argument parser
    parser = argparse.ArgumentParser(description="Script that processes a subtitle file")

    # Add a folder argument
    parser.add_argument('--subtitle', type=str, help="Path to the subtitle folder to be processed",
                        default=r"records")
    # Add default tts speeds file
    parser.add_argument('--speeds', type=str, help="Path to the speeds of tts",
                        default="speeds.csv")
    # Add delay to think that must be only one sentences, default value very very low
    parser.add_argument('--delay', type=float, help="Delay to think that must be only one sentences",
                        default=0.00001) 
    # Add voice
    parser.add_argument('--voice', type=str, help="Path to voice", default="basic_ref_en.wav")
    # Add text
    parser.add_argument('--text', type=str, help="Path to text for voice", default="some call me nature, others call me mother nature.")
    # Add voice coeficient
    parser.add_argument('--coef', type=float, help="Voice coeficient", default=0.2)
    # Add video extension
    parser.add_argument('--videoext', type=str, help="Video extension of video files", default=".mp4")
    # Add subtitles extension
    parser.add_argument('--srtext', type=str, help="Subtitle extension of files", default=".srt")
    # Add out video ending
    parser.add_argument('--outfileending', type=str, help="Out video file ending", default="_out_mix.mp4")
    # Add vocabular
    parser.add_argument('--vocabular', type=str, help="Vocabular of transcriptions", default="vocabular.txt")
    # Add config
    parser.add_argument('--config', "-c", type=str, help="Config file", default="basic.toml")

    # Parse the arguments
    args = parser.parse_args()

    # Extract the folder argument
    subtitle = args.subtitle
    speeds = args.speeds
    delay = args.delay
    voice = args.voice
    text = args.text
    coef = args.coef
    videoext = args.videoext
    srtext = args.srtext
    outfileending = args.outfileending
    vocabular = args.vocabular

    print(f"Processing folder: {subtitle}")

    voice_dir = Path(subtitle)/"VOICE"

    vocabular_pth = check_vocabular(voice_dir)
    check_texts(voice_dir)
    check_speeds_csv(voice_dir)

    speakers = get_speakers_from_folder(voice_dir)
    if not speakers:
        print("I need at least one speaker.")
        exit(1)
    default_speaker = speakers.get(speakers["default_speaker_name"])

    sbt_files = fast_rglob(subtitle, srtext, exclude_ext="_0_mod.srt")
    # we need exclude srt modified files that we used for right pronunciation

    for subtitle in sbt_files:
        subtitle = Path(subtitle)
        video_path = subtitle.with_suffix(videoext)
        ready_video_file_name = subtitle.stem + "_out_mix.mp4"
        ready_video_path = video_path.parent / ready_video_file_name
        if video_path.is_file() and not ready_video_path.is_file():
            make_video_from(video_path, subtitle, speakers, default_speaker, vocabular_pth, coef)



if __name__ == "__main__":
    main()


