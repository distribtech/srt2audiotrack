"""Utility functions extracted from main.py."""

import os
from pathlib import Path
import librosa

from . import subtitle_csv
from . import tts_audio
from . import sync_utils
from . import audio_utils
from . import ffmpeg_utils
from . import vocabulary
from .audio_utils import (
    convert_mono_to_stereo,
    normalize_stereo_audio,
    extract_acomponiment_or_vocals,
    adjust_stereo_volume_with_librosa,
)

class SubtitlePipeline:
    """Pipeline for generating English voice-over for a subtitle-video pair."""

    def __init__(
        self,
        subtitle: Path | str,
        vocabular: Path | str,
        speakers: dict,
        default_speaker: dict,
        acomponiment_coef: float,
        voice_coef: float,
        output_folder: str | Path = "",
    ) -> None:
        # Convert string paths to Path objects if needed
        self.subtitle = Path(subtitle) if isinstance(subtitle, str) else subtitle
        self.vocabular = Path(vocabular) if isinstance(vocabular, str) else vocabular
        
        # If output_folder is empty or not provided, use the subtitle's parent directory
        if not output_folder:
            self.output_folder = self.subtitle.parent
        else:
            self.output_folder = Path(output_folder) if isinstance(output_folder, str) else output_folder
            
        self.speakers = speakers
        self.default_speaker = default_speaker
        self.acomponiment_coef = acomponiment_coef
        self.voice_coef = voice_coef
        self.subtitle_name: str = self.subtitle.stem

        self.directory: Path = self.output_folder / self.subtitle.stem

        # Output artifacts
        self.out_path = self.directory / f"{self.subtitle_name}_0_mod.srt"

        self.srt_csv_file = self.directory / f"{self.subtitle_name}_1.0_srt.csv"
        self.output_csv_with_speakers = self.directory / f"{self.subtitle_name}_1.5_output_speakers.csv"
        self.output_with_preview_speeds_csv = self.directory / f"{self.subtitle_name}_3.0_output_speed.csv"
        self.corrected_time_output_speed_csv = self.directory / f"{self.subtitle_name}_4_corrected_output_speed.csv"

        self.output_audio_file = self.directory / f"{self.subtitle_name}_5.0_output_audiotrack_eng.wav"
        self.stereo_eng_file = self.directory / f"{self.subtitle_name}_5.3_stereo_eng.wav"
        self.out_ukr_wav = self.directory / f"{self.subtitle_name}_5.5_out_ukr.wav"
        self.acomponiment = self.directory / f"{self.subtitle_name}_5.7_accompaniment_ukr.wav"
        self.output_ukr_wav = self.directory / f"{self.subtitle_name}_6_out_reduced_ukr.wav"
        
        self.mix_video = self.output_folder / f"{self.subtitle_name}_out_mix.mp4"
        self.sample_rate = None

    def run(self, video_path: str) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        # Use public wrappers so that behaviour can be monkeypatched in tests
        self.directory.mkdir(parents=True, exist_ok=True)
        self._prepare_subtitles()

        self._convert_subs_to_audio()
        self.process_video_file(video_path)

    # ------------------------------------------------------------------
    # Public wrappers used by tests and external callers
    # ------------------------------------------------------------------

    # def prepare_subtitles(self) -> tuple[Path, str, Path]:
    #     """Prepare subtitle file and return paths.

    #     Returns
    #     -------
    #     tuple[Path, str, Path]
    #         The working directory, subtitle name and modified subtitle path.
    #     """
    #     self.directory.mkdir(parents=True, exist_ok=True)
    #     self._prepare_subtitles()
    #     return self.directory, self.subtitle_name, self.out_path

    # def subtitles_to_audio(self) -> tuple[Path, Path]:
    #     """Convert prepared subtitles to audio files."""
    #     self._convert_subs_to_audio()
    #     return self.srt_csv_file, self.stereo_eng_file

    def process_video_file(self, video_path: str) -> None:
        """Process a video file using already generated audio tracks."""
        self._extract_ukrainian_audio(video_path)
        self._separate_accompaniment()
        self._adjust_volume()
        self._mix_video(video_path)

    def _prepare_subtitles(self) -> None:
        if not self.out_path.exists():
            vocabulary.modify_subtitles_with_vocabular_text_only(self.subtitle, self.vocabular, self.out_path)

    def _convert_subs_to_audio(self) -> None:
        if not self.srt_csv_file.exists():
            subtitle_csv.srt_to_csv(self.out_path, self.srt_csv_file)

        if not self.output_csv_with_speakers.exists():
            subtitle_csv.add_speaker_columns(self.srt_csv_file, self.output_csv_with_speakers)

        if not self.output_with_preview_speeds_csv.exists():
            subtitle_csv.add_speed_columns_with_speakers(
                self.output_csv_with_speakers, self.speakers, self.output_with_preview_speeds_csv
            )

        if not tts_audio.F5TTS.all_segments_in_folder_check(self.output_with_preview_speeds_csv, self.directory):
            tts_audio.F5TTS().generate_from_csv_with_speakers(
                self.output_with_preview_speeds_csv,
                self.directory,
                self.speakers,
                self.default_speaker,
                rewrite=False,
            )

        if not self.corrected_time_output_speed_csv.exists():
            sync_utils.correct_end_times_in_csv(
                self.directory,
                self.output_with_preview_speeds_csv,
                self.corrected_time_output_speed_csv,
            )

        if not self.output_audio_file.exists():
            audio_utils.collect_full_audiotrack(
                self.directory,
                self.corrected_time_output_speed_csv,
                self.output_audio_file,
            )

        if not self.stereo_eng_file.exists():
            convert_mono_to_stereo(self.output_audio_file, self.stereo_eng_file)

    def _extract_ukrainian_audio(self, video_path: str) -> None:
        if not self.out_ukr_wav.exists():
            ffmpeg_utils.extract_audio(video_path, self.out_ukr_wav)

    def _separate_accompaniment(self) -> None:
        if not self.acomponiment.exists():
            self.sample_rate = librosa.get_samplerate(self.out_ukr_wav)
            extracted = extract_acomponiment_or_vocals(
                self.directory, self.subtitle_name, self.out_ukr_wav,
                sample_rate=self.sample_rate)
            normalize_stereo_audio(extracted, self.acomponiment)
            os.remove(extracted)

    def _adjust_volume(self) -> None:
        if not self.output_ukr_wav.exists():
            volume_intervals = ffmpeg_utils.parse_volume_intervals(self.srt_csv_file)
            normalize_stereo_audio(self.acomponiment, self.output_ukr_wav)
            adjust_stereo_volume_with_librosa(
                self.acomponiment,
                self.output_ukr_wav,
                volume_intervals,
                self.acomponiment,
                self.acomponiment_coef,
                self.voice_coef,
            )

    def _mix_video(self, video_path: str) -> None:
        ext = Path(video_path).suffix.lower()
        self.mix_video = self.directory.parent / f"{self.subtitle_name}_out_mix{ext}"
        if not self.mix_video.exists():
            ffmpeg_utils.create_ffmpeg_mix_video(video_path, self.output_ukr_wav, self.stereo_eng_file, self.mix_video)

    @staticmethod
    def list_subtitle_files(root_dir: str | Path, extension: str, exclude_ext: str) -> list[str]:
        ext = extension.lstrip('.')
        return [
            str(p)
            for p in Path(root_dir).rglob(f'*.{ext}')
            if not str(p).endswith(exclude_ext)
        ]

    @staticmethod
    def create_video_with_english_audio(
        video_path: str,
        subtitle: Path,
        speakers: dict,
        default_speaker: dict,
        vocabular: Path,
        acomponiment_coef: float,
        voice_coef: float,
        output_folder: Path,
    ) -> None:
        """Convenience wrapper used by ``main.py`` for processing a single video."""
        pipeline = SubtitlePipeline(
            subtitle,
            vocabular,
            speakers,
            default_speaker,
            acomponiment_coef,
            voice_coef,
            output_folder,
        )
        pipeline.run(video_path)



