"""Utility functions extracted from main.py."""

import os
from pathlib import Path

import subtitle_csv
import tts_audio
import sync_utils
import audio_utils
import ffmpeg_utils
import vocabulary
from audio_utils import (
    convert_mono_to_stereo,
    normalize_stereo_audio,
    extract_acomponiment_or_vocals,
)


def prepare_subtitles(subtitle: Path, vocabular_pth: Path, output_folder: Path):
    """Apply vocabulary corrections and return helper paths.

    All intermediate files are written inside ``output_folder`` under a
    subdirectory named after the subtitle file stem.
    """

    directory = Path(output_folder) / subtitle.stem
    directory.mkdir(parents=True, exist_ok=True)
    subtitle_name = subtitle.stem
    out_path = directory / f"{subtitle_name}_0_mod.srt"

    if not out_path.exists():
        vocabulary.modify_subtitles_with_vocabular_text_only(
            subtitle, vocabular_pth, out_path
        )

    return directory, subtitle_name, out_path


def subtitles_to_audio(directory: Path, subtitle_name: str, out_path: Path, speakers: dict, default_speaker: dict):
    """Convert subtitles to CSV and generate English audio."""
    srt_csv_file = directory / f"{subtitle_name}_1.0_srt.csv"
    if not srt_csv_file.exists():
        subtitle_csv.srt_to_csv(out_path, srt_csv_file)

    output_csv_with_speakers = directory / f"{subtitle_name}_1.5_output_speakers.csv"
    if not output_csv_with_speakers.exists():
        subtitle_csv.add_speaker_columns(srt_csv_file, output_csv_with_speakers)

    output_with_preview_speeds_csv = directory / f"{subtitle_name}_3.0_output_speed.csv"
    if not output_with_preview_speeds_csv.exists():
        subtitle_csv.add_speed_columns_with_speakers(
            output_csv_with_speakers, speakers, output_with_preview_speeds_csv
        )

    if not tts_audio.F5TTS.all_segments_in_folder_check(
        output_with_preview_speeds_csv, directory
    ):
        f5tts = tts_audio.F5TTS()
        f5tts.generate_from_csv_with_speakers(
            output_with_preview_speeds_csv,
            directory,
            speakers,
            default_speaker,
            rewrite=False,
        )

    corrected_time_output_speed_csv = directory / f"{subtitle_name}_4_corrected_output_speed.csv"
    if not corrected_time_output_speed_csv.exists():
        sync_utils.correct_end_times_in_csv(
            directory, output_with_preview_speeds_csv, corrected_time_output_speed_csv
        )

    output_audio_file = directory / f"{subtitle_name}_5.0_output_audiotrack_eng.wav"
    if not output_audio_file.exists():
        audio_utils.collect_full_audiotrack(
            directory, corrected_time_output_speed_csv, output_audio_file
        )

    stereo_eng_file = directory / f"{subtitle_name}_5.3_stereo_eng.wav"
    if not stereo_eng_file.exists():
        convert_mono_to_stereo(output_audio_file, stereo_eng_file)

    return srt_csv_file, stereo_eng_file


def process_video_file(
    video_path: str,
    directory: Path,
    subtitle_name: str,
    srt_csv_file: Path,
    stereo_eng_file: Path,
    coef: float,
):
    """Process the input video and mix with generated audio."""
    if not os.path.exists(video_path):
        return

    out_ukr_wav = directory / f"{subtitle_name}_5.5_out_ukr.wav"
    if not out_ukr_wav.exists():
        command = ffmpeg_utils.extract_audio(video_path, out_ukr_wav)
        ffmpeg_utils.run(command)

    acomponiment = directory / f"{subtitle_name}_5.7_accompaniment_ukr.wav"
    if not acomponiment.exists():
        acomponiment_extracted = extract_acomponiment_or_vocals(
            directory, subtitle_name, out_ukr_wav
        )
        normalize_stereo_audio(acomponiment_extracted, acomponiment)
        os.remove(acomponiment_extracted)

    output_audio = directory / f"{subtitle_name}_6_out_reduced_ukr.wav"
    if not output_audio.exists():
        volume_intervals = ffmpeg_utils.parse_volume_intervals(srt_csv_file)
        normalize_stereo_audio(out_ukr_wav, out_ukr_wav)
        ffmpeg_utils.adjust_stereo_volume_with_librosa(
            out_ukr_wav, output_audio, volume_intervals, acomponiment,  coef
        )

    ext = Path(video_path).suffix.lower()
    match ext:
        case ".mp4" | ".mkv" | ".avi":
            mix_video = directory.parent / f"{subtitle_name}_out_mix{ext}"
        case _:
            print(f"Unsupported video format: {video_path}")
            return

    if not mix_video.exists():
        command = ffmpeg_utils.create_ffmpeg_mix_video_file_command(
            video_path, output_audio, stereo_eng_file, mix_video
        )
        ffmpeg_utils.run(command)


def create_video_with_english_audio(
    video_path: str,
    subtitle: Path,
    speakers: dict,
    default_speaker: dict,
    vocabular_pth: Path,
    coef: float,
    output_folder: Path,
):
    directory, subtitle_name, out_path = prepare_subtitles(subtitle, vocabular_pth, output_folder)
    srt_csv_file, stereo_eng_file = subtitles_to_audio(
        directory, subtitle_name, out_path, speakers, default_speaker
    )
    process_video_file(
        video_path, directory, subtitle_name, srt_csv_file, stereo_eng_file, coef
    )


def list_subtitle_files(root_dir: str | Path, extension: str, exclude_ext: str):
    """Recursively search for files with the given extension, excluding modified files."""
    ext = extension.lstrip('.')
    sbt_files = []
    for dirpath, _, filenames in os.walk(root_dir):
        for file in filenames:
            if file.endswith(f".{ext}") and not file.endswith(exclude_ext):
                sbt_files.append(os.path.join(dirpath, file))
    return sbt_files

