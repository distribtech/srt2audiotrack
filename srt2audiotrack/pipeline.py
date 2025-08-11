"""Functional pipeline utilities for generating English voice-over."""

from __future__ import annotations

import os
from pathlib import Path
import librosa

from . import subtitle_csv, tts_audio, sync_utils, audio_utils, ffmpeg_utils, vocabulary
from .audio_utils import (
    convert_mono_to_stereo,
    normalize_stereo_audio,
    extract_acomponiment_or_vocals,
    adjust_stereo_volume_with_librosa,
)


def prepare_subtitles(
    subtitle: Path | str,
    vocabular: Path | str,
    output_folder: str | Path = "",
) -> tuple[Path, str, Path]:
    """Prepare subtitle file and return working directory information.

    Parameters
    ----------
    subtitle:
        Path to the original subtitle file.
    vocabular:
        Path to the vocabulary file used for corrections.
    output_folder:
        Optional folder where all intermediate artifacts will be placed.  If
        omitted the subtitle's parent directory is used.

    Returns
    -------
    tuple[Path, str, Path]
        The working directory, subtitle name and path to the modified subtitle
        file.
    """

    subtitle = Path(subtitle)
    vocabular = Path(vocabular)
    output_dir = Path(output_folder) if output_folder else subtitle.parent

    directory = output_dir / subtitle.stem
    directory.mkdir(parents=True, exist_ok=True)

    out_path = directory / f"{subtitle.stem}_0_mod.srt"
    if not out_path.exists():
        vocabulary.modify_subtitles_with_vocabular_text_only(subtitle, vocabular, out_path)

    return directory, subtitle.stem, out_path


def subtitles_to_audio(
    directory: Path,
    subtitle_name: str,
    out_path: Path,
    speakers: dict,
    default_speaker: dict,
    tts_language,
) -> tuple[Path, Path]:
    """Convert prepared subtitles to audio files.

    Returns
    -------
    tuple[Path, Path]
        Path to the CSV with subtitle timings and path to the generated stereo
        English audio file.
    """

    srt_csv_file = directory / f"{subtitle_name}_1.0_srt.csv"
    output_csv_with_speakers = directory / f"{subtitle_name}_1.5_output_speakers.csv"
    output_with_preview_speeds_csv = directory / f"{subtitle_name}_3.0_output_speed.csv"
    corrected_time_output_speed_csv = directory / f"{subtitle_name}_4_corrected_output_speed.csv"
    output_audio_file = directory / f"{subtitle_name}_5.0_output_audiotrack_eng.wav"
    stereo_eng_file = directory / f"{subtitle_name}_5.3_stereo_eng.wav"

    if not srt_csv_file.exists():
        subtitle_csv.srt_to_csv(out_path, srt_csv_file)

    if not output_csv_with_speakers.exists():
        subtitle_csv.add_speaker_columns(srt_csv_file, output_csv_with_speakers)

    if not output_with_preview_speeds_csv.exists():
        subtitle_csv.add_speed_columns_with_speakers(
            output_csv_with_speakers, speakers, output_with_preview_speeds_csv
        )

    if not tts_audio.F5TTS.all_segments_in_folder_check(
        output_with_preview_speeds_csv, directory
    ):
        tts_audio.F5TTS(language=tts_language).generate_from_csv_with_speakers(
            output_with_preview_speeds_csv,
            directory,
            speakers,
            default_speaker,
            rewrite=False,
        )

    if not corrected_time_output_speed_csv.exists():
        sync_utils.correct_end_times_in_csv(
            directory,
            output_with_preview_speeds_csv,
            corrected_time_output_speed_csv,
        )

    if not output_audio_file.exists():
        audio_utils.collect_full_audiotrack(
            directory,
            corrected_time_output_speed_csv,
            output_audio_file,
        )

    if not stereo_eng_file.exists():
        convert_mono_to_stereo(output_audio_file, stereo_eng_file)

    return srt_csv_file, stereo_eng_file


def process_video_file(
    video_path: str,
    directory: Path,
    subtitle_name: str,
    srt_csv_file: Path,
    stereo_eng_file: Path,
    acomponiment_coef: float,
    voice_coef: float,
) -> None:
    """Process a video file using already generated audio tracks."""

    out_ukr_wav = directory / f"{subtitle_name}_5.5_out_ukr.wav"
    acomponiment = directory / f"{subtitle_name}_5.7_accompaniment_ukr.wav"
    output_ukr_wav = directory / f"{subtitle_name}_6_out_reduced_ukr.wav"

    if not out_ukr_wav.exists():
        ffmpeg_utils.extract_audio(video_path, out_ukr_wav)

    if not acomponiment.exists():
        sample_rate = librosa.get_samplerate(out_ukr_wav)
        extracted = extract_acomponiment_or_vocals(
            directory, subtitle_name, out_ukr_wav, sample_rate=sample_rate
        )
        normalize_stereo_audio(extracted, acomponiment)
        os.remove(extracted)

    if not output_ukr_wav.exists():
        volume_intervals = ffmpeg_utils.parse_volume_intervals(srt_csv_file)
        normalize_stereo_audio(acomponiment, output_ukr_wav)
        adjust_stereo_volume_with_librosa(
            out_ukr_wav,
            acomponiment,
            output_ukr_wav,
            volume_intervals,
            acomponiment,
            acomponiment_coef,
            voice_coef,
        )

    ext = Path(video_path).suffix.lower()
    mix_video = directory.parent / f"{subtitle_name}_out_mix{ext}"
    if not mix_video.exists():
        ffmpeg_utils.create_ffmpeg_mix_video(
            video_path, output_ukr_wav, stereo_eng_file, mix_video
        )


def run_pipeline(
    video_path: str,
    subtitle: Path | str,
    speakers: dict,
    default_speaker: dict,
    vocabular: Path | str,
    acomponiment_coef: float,
    voice_coef: float,
    tts_language: str,
    output_folder: Path | str = ""    
) -> None:
    """Run the complete processing pipeline for a single video."""

    directory, subtitle_name, out_path = prepare_subtitles(
        subtitle, vocabular, output_folder
    )
    srt_csv_file, stereo_eng_file = subtitles_to_audio(
        directory, subtitle_name, out_path, speakers, default_speaker, tts_language
    )
    process_video_file(
        video_path,
        directory,
        subtitle_name,
        srt_csv_file,
        stereo_eng_file,
        acomponiment_coef,
        voice_coef,
    )


def list_subtitle_files(root_dir: str | Path, extension: str, exclude_ext: str) -> list[str]:
    """Return subtitle files from ``root_dir`` with given ``extension``."""

    ext = extension.lstrip(".")
    return [
        str(p)
        for p in Path(root_dir).rglob(f"*.{ext}")
        if not str(p).endswith(exclude_ext)
    ]


def create_video_with_english_audio(
    video_path: str,
    subtitle: Path,
    speakers: dict,
    default_speaker: dict,
    vocabular: Path,
    acomponiment_coef: float,
    voice_coef: float,
    output_folder: Path,
    tts_language: str = "en",
) -> None:
    """Convenience wrapper used by ``main.py`` for processing a single video."""

    run_pipeline(
        video_path,
        subtitle,
        speakers,
        default_speaker,
        vocabular,
        acomponiment_coef,
        voice_coef,
        output_folder,
        tts_language,
    )

