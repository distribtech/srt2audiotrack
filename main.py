import argparse
import os
from pathlib import Path


import srt2csv
import srt2audio
import correct_times
import wavs2wav
import ffmpeg_commands
import vocabular
from wavs2wav import (
    convert_mono_to_stereo,
    normalize_stereo_audio,
    extract_accompaniment_or_vocals,
)
from srt2csv import get_speakers_from_folder, check_texts, check_speeds_csv
from vocabular import check_vocabular


def modify_subtitles(subtitle, vocabular_pth, directory):
    subtitle_name = subtitle.stem
    out_path = directory / f"{subtitle_name}_0_mod.srt"
    if not out_path.exists():
        vocabular.modify_subtitles_with_vocabular_wholefile(
            subtitle, vocabular_pth, out_path
        )
    return out_path


def convert_to_csv(out_path, directory, subtitle_name):
    srt_csv_file = directory / f"{subtitle_name}_1.0_srt.csv"
    if not srt_csv_file.exists():
        srt2csv.srt_to_csv(out_path, srt_csv_file)
    return srt_csv_file


def prepare_csv_with_speeds(srt_csv_file, speakers, directory, subtitle_name):
    output_csv_with_speakers = directory / f"{subtitle_name}_1.5_output_speakers.csv"
    if not output_csv_with_speakers.exists():
        srt2csv.add_speaker_columns(srt_csv_file, output_csv_with_speakers)

    output_with_preview_speeds_csv = directory / f"{subtitle_name}_3.0_output_speed.csv"
    if not output_with_preview_speeds_csv.exists():
        srt2csv.add_speed_columns_with_speakers(
            output_csv_with_speakers, speakers, output_with_preview_speeds_csv
        )
    return output_with_preview_speeds_csv


def generate_audio_if_needed(output_csv, directory, speakers):
    if not srt2audio.F5TTS.all_segments_in_folder_check(output_csv, directory):
        f5tts = srt2audio.F5TTS()
        default_speaker_name = speakers["default_speaker_name"]
        default_speaker = speakers[default_speaker_name]
        f5tts.generate_from_csv_with_speakers(
            output_csv, directory, speakers, default_speaker, rewrite=False
        )


def correct_timings(directory, output_csv, subtitle_name):
    corrected_csv = directory / f"{subtitle_name}_4_corrected_output_speed.csv"
    if not corrected_csv.exists():
        correct_times.correct_end_times_in_csv(
            directory, output_csv, corrected_csv
        )
    return corrected_csv


def build_audio_track(directory, corrected_csv, subtitle_name):
    output_audio_file = directory / f"{subtitle_name}_5.0_output_audiotrack_eng.wav"
    if not output_audio_file.exists():
        wavs2wav.collect_full_audiotrack(directory, corrected_csv, output_audio_file)

    stereo_eng_file = directory / f"{subtitle_name}_5.3_stereo_eng.wav"
    if not stereo_eng_file.exists():
        convert_mono_to_stereo(output_audio_file, stereo_eng_file)
    return stereo_eng_file


def handle_video(video_path, directory, subtitle_name, srt_csv_file, stereo_eng_file, coef):
    if not os.path.exists(video_path):
        return

    out_ukr_wav = directory / f"{subtitle_name}_5.5_out_ukr.wav"
    if not out_ukr_wav.exists():
        match Path(video_path).suffix.lower():
            case ".mp4" | ".mkv" | ".avi" | ".mov":
                command = ffmpeg_commands.extract_audio(video_path, out_ukr_wav)
                ffmpeg_commands.run(command)
            case _:
                raise ValueError(f"Unsupported video format: {video_path.suffix}")

    accompaniment = directory / f"{subtitle_name}_5.7_accompaniment_ukr.wav"
    if not accompaniment.exists():
        accompaniment_extracted = extract_accompaniment_or_vocals(
            directory, subtitle_name, out_ukr_wav
        )
        normalize_stereo_audio(accompaniment_extracted, accompaniment)
        os.remove(accompaniment_extracted)

    output_audio = directory / f"{subtitle_name}_6_out_reduced_ukr.wav"
    if not output_audio.exists():
        volume_intervals = ffmpeg_commands.parse_volume_intervals(srt_csv_file)
        normalize_stereo_audio(out_ukr_wav, out_ukr_wav)
        ffmpeg_commands.adjust_stereo_volume_with_librosa(
            out_ukr_wav, output_audio, volume_intervals, coef, accompaniment
        )

    mix_video = directory.parent / f"{subtitle_name}_out_mix.mp4"
    if not mix_video.exists():
        command = ffmpeg_commands.create_ffmpeg_mix_video_file_command(
            video_path, output_audio, stereo_eng_file, mix_video
        )
        ffmpeg_commands.run(command)



def make_video_from(video_path, subtitle, speakers, default_speaker, vocabular_pth, coef):
    directory = subtitle.with_suffix("")
    directory.mkdir(exist_ok=True)
    subtitle_name = subtitle.stem

    lock_file = directory / f"{subtitle_name}.lock"
    try:
        fd = os.open(lock_file, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.close(fd)
    except FileExistsError:
        print(f"Skip {subtitle} because lock file exists")
        return

    try:
        out_path = modify_subtitles(subtitle, vocabular_pth, directory)
        srt_csv_file = convert_to_csv(out_path, directory, subtitle_name)
        output_with_preview_speeds_csv = prepare_csv_with_speeds(
            srt_csv_file, speakers, directory, subtitle_name
        )
        generate_audio_if_needed(output_with_preview_speeds_csv, directory, speakers)
        corrected_csv = correct_timings(directory, output_with_preview_speeds_csv, subtitle_name)
        stereo_eng_file = build_audio_track(directory, corrected_csv, subtitle_name)
        handle_video(
            video_path,
            directory,
            subtitle_name,
            srt_csv_file,
            stereo_eng_file,
            coef,
        )
    finally:
        if lock_file.exists():
            os.remove(lock_file)

def fast_rglob(root_dir, extension, exclude_ext):  # for network drives
    """Recursively find files matching ``extension`` under ``root_dir``.

    Parameters
    ----------
    root_dir : str or Path
        The directory tree to search.
    extension : str
        File extension to match (e.g., ``".srt"``).
    exclude_ext : str
        Suffix to exclude from results.

    Returns
    -------
    list[str]
        Paths to all matching files.

    Notes
    -----
    ``pathlib.Path.rglob`` was noticeably slow on large network drives. This
    helper relies on ``os.walk`` which performs better in that environment.
    """
    ext = extension.lstrip('.')
    sbt_files = []
    for dirpath, _, filenames in os.walk(root_dir):
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

    subtitle_path = Path(subtitle)
    root_dir = subtitle_path.parent if subtitle_path.is_file() else subtitle_path

    print(f"Processing folder: {root_dir}")

    voice_dir = root_dir/"VOICE"

    vocabular_pth = check_vocabular(voice_dir)
    check_texts(voice_dir)
    check_speeds_csv(voice_dir)

    speakers = get_speakers_from_folder(voice_dir)
    if not speakers:
        print("I need at least one speaker.")
        exit(1)
    default_speaker = speakers.get(speakers["default_speaker_name"])

    if subtitle_path.is_file():
        sbt_files = [subtitle_path]
    else:
        sbt_files = fast_rglob(subtitle_path, srtext, exclude_ext="_0_mod.srt")
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


