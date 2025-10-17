"""Utility functions extracted from main.py."""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path
import librosa

from . import subtitle_csv
from . import tts_audio
from . import sync_utils
from . import audio_utils
from . import ffmpeg_utils
from . import vocabulary

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
        *,
        vocabulary_module=vocabulary,
        subtitle_csv_module=subtitle_csv,
        tts_audio_module=tts_audio,
        sync_utils_module=sync_utils,
        audio_utils_module=audio_utils,
        ffmpeg_utils_module=ffmpeg_utils,
        librosa_module=librosa,
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

        self.output_audio_file = self.directory / f"{self.subtitle_name}_5.0_output_audiotrack_eng.flac"
        self.stereo_eng_file = self.directory / f"{self.subtitle_name}_5.3_stereo_eng.flac"
        self.out_ukr_audio = self.directory / f"{self.subtitle_name}_5.5_out_ukr.flac"
        self.acomponiment = self.directory / f"{self.subtitle_name}_5.7_accompaniment_ukr.flac"
        self.output_ukr_audio = self.directory / f"{self.subtitle_name}_6_out_reduced_ukr.flac"
        
        self.mix_video = self.output_folder / f"{self.subtitle_name}_out_mix.mp4"
        self.sample_rate = None

        self.vocabulary = vocabulary_module
        self.subtitle_csv = subtitle_csv_module
        self.tts_audio = tts_audio_module
        self.sync_utils = sync_utils_module
        self.audio_utils = audio_utils_module
        self.ffmpeg_utils = ffmpeg_utils_module
        self.librosa = librosa_module

    def run(self, video_path: str) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        self._prepare_subtitles()

        self._convert_subs_to_audio()
        self.process_video_file(video_path)

    def process_video_file(self, video_path: str) -> None:
        """Process a video file using already generated audio tracks."""
        self._extract_ukrainian_audio(video_path)
        self._separate_accompaniment()
        self._adjust_volume()
        self._mix_video(video_path)

    def _prepare_subtitles(self) -> None:
        if not self.out_path.exists():
            self.vocabulary.modify_subtitles_with_vocabular_text_only(
                self.subtitle,
                self.vocabular,
                self.out_path,
            )

    def _convert_subs_to_audio(self) -> None:
        if not self.srt_csv_file.exists():
            self.subtitle_csv.srt_to_csv(self.out_path, self.srt_csv_file)

        if not self.output_csv_with_speakers.exists():
            self.subtitle_csv.add_speaker_columns(self.srt_csv_file, self.output_csv_with_speakers)

        if not self.output_with_preview_speeds_csv.exists():
            self.subtitle_csv.add_speed_columns_with_speakers(
                self.output_csv_with_speakers, self.speakers, self.output_with_preview_speeds_csv
            )

        if not self.tts_audio.F5TTS.all_segments_in_folder_check(
            self.output_with_preview_speeds_csv,
            self.directory,
        ):
            self.tts_audio.F5TTS().generate_from_csv_with_speakers(
                self.output_with_preview_speeds_csv,
                self.directory,
                self.speakers,
                self.default_speaker,
                rewrite=False,
            )

        if not self.corrected_time_output_speed_csv.exists():
            self.sync_utils.correct_end_times_in_csv(
                self.directory,
                self.output_with_preview_speeds_csv,
                self.corrected_time_output_speed_csv,
            )

        if not self.output_audio_file.exists():
            self.audio_utils.collect_full_audiotrack(
                self.directory,
                self.corrected_time_output_speed_csv,
                self.output_audio_file,
            )

        if not self.stereo_eng_file.exists():
            self.audio_utils.convert_mono_to_stereo(self.output_audio_file, self.stereo_eng_file)

    def _extract_ukrainian_audio(self, video_path: str) -> None:
        if not self.out_ukr_audio.exists():
            self.ffmpeg_utils.extract_audio(video_path, self.out_ukr_audio)

    def _separate_accompaniment(self) -> None:
        if not self.acomponiment.exists():
            self.sample_rate = self.librosa.get_samplerate(self.out_ukr_audio)
            extracted = self.audio_utils.extract_acomponiment_or_vocals(
                self.directory,
                self.subtitle_name,
                self.out_ukr_audio,
                sample_rate=self.sample_rate,
            )
            self.audio_utils.normalize_stereo_audio(extracted, self.acomponiment)
            os.remove(extracted)

    def _adjust_volume(self) -> None:
        if not self.output_ukr_audio.exists():
            volume_intervals = self.ffmpeg_utils.parse_volume_intervals(self.srt_csv_file)
            self.audio_utils.normalize_stereo_audio(self.acomponiment, self.output_ukr_audio)
            self.audio_utils.adjust_stereo_volume_with_librosa(
                self.out_ukr_audio,
                self.acomponiment,
                self.output_ukr_audio,
                volume_intervals,
                self.acomponiment,
                self.acomponiment_coef,
                self.voice_coef,
            )

    def _mix_video(self, video_path: str) -> None:
        ext = Path(video_path).suffix.lower()
        self.mix_video = self.directory.parent / f"{self.subtitle_name}_out_mix{ext}"
        if not self.mix_video.exists():
            self.ffmpeg_utils.create_ffmpeg_mix_video(
                video_path,
                self.output_ukr_audio,
                self.stereo_eng_file,
                self.mix_video,
            )

    @staticmethod
    def list_subtitle_files(root_dir: str | Path, extension: str, exclude_ext: str) -> list[str]:
        ext = extension.lstrip('.')
        return [
            str(p)
            for p in Path(root_dir).rglob(f'*.{ext}')
            if not str(p).endswith(exclude_ext)
        ]

    @classmethod
    def create_video_with_english_audio(
        cls,
        video_path: str,
        subtitle: Path,
        speakers: dict,
        default_speaker: dict,
        vocabular: Path,
        acomponiment_coef: float,
        voice_coef: float,
        output_folder: Path,
        *,
        pipeline_factory: Callable[..., "SubtitlePipeline"] | None = None,
        pipeline_kwargs: dict | None = None,
    ) -> None:
        """Convenience wrapper used by ``main.py`` for processing a single video."""

        factory = pipeline_factory or cls
        pipeline_arguments = {
            "subtitle": subtitle,
            "vocabular": vocabular,
            "speakers": speakers,
            "default_speaker": default_speaker,
            "acomponiment_coef": acomponiment_coef,
            "voice_coef": voice_coef,
            "output_folder": output_folder,
        }
        if pipeline_kwargs:
            pipeline_arguments.update(pipeline_kwargs)

        pipeline = factory(**pipeline_arguments)
        pipeline.run(video_path)



