from __future__ import annotations

from pathlib import Path
import os
import sys
import types
from types import SimpleNamespace

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

librosa_stub = types.ModuleType("librosa")
librosa_stub.get_samplerate = lambda *_args, **_kwargs: 1
sys.modules["librosa"] = librosa_stub

for name in ["subtitle_csv", "tts_audio", "sync_utils", "ffmpeg_utils", "audio_utils"]:
    sys.modules[f"srt2audiotrack.{name}"] = types.ModuleType(name)

from srt2audiotrack.pipeline import SubtitlePipeline


def _touch(path: Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("stub")


def _make_dependencies() -> dict:
    def modify_subtitles_with_vocabular_text_only(_subtitle: Path, _vocab: Path, out_path: Path) -> None:
        Path(out_path).write_text("modified")

    vocabulary_module = SimpleNamespace(
        modify_subtitles_with_vocabular_text_only=modify_subtitles_with_vocabular_text_only
    )

    def srt_to_csv(_src: Path, dest: Path) -> None:
        Path(dest).write_text("Start Time\n00:00:00,000")

    def add_speaker_columns(_src: Path, dest: Path) -> None:
        Path(dest).write_text("speaker")

    def add_speed_columns_with_speakers(_src: Path, _speakers: dict, dest: Path) -> None:
        Path(dest).write_text("speed")

    subtitle_csv_module = SimpleNamespace(
        srt_to_csv=srt_to_csv,
        add_speaker_columns=add_speaker_columns,
        add_speed_columns_with_speakers=add_speed_columns_with_speakers,
    )

    class StubF5TTS:
        @staticmethod
        def all_segments_in_folder_check(_csv_file: Path, _folder: Path) -> bool:
            return True

        def generate_from_csv_with_speakers(self, *_args, **_kwargs) -> None:  # pragma: no cover - stub
            return None

    tts_audio_module = SimpleNamespace(F5TTS=StubF5TTS)

    def correct_end_times_in_csv(_directory: Path, _src: Path, dest: Path) -> None:
        Path(dest).write_text("corrected")

    sync_utils_module = SimpleNamespace(correct_end_times_in_csv=correct_end_times_in_csv)

    def collect_full_audiotrack(_directory: Path, _csv_file: Path, output_audio_file: Path) -> None:
        _touch(output_audio_file)

    def convert_mono_to_stereo(_input_path: Path, output_path: Path) -> None:
        _touch(output_path)

    def normalize_stereo_audio(_input_path: Path, output_path: Path, *_args, **_kwargs) -> None:
        _touch(output_path)

    def extract_acomponiment_or_vocals(
        directory: Path,
        subtitle_name: str,
        _out_ukr_audio: Path,
        *,
        sample_rate: int,
        **_kwargs,
    ) -> Path:
        temp = Path(directory) / f"{subtitle_name}_temp.flac"
        _touch(temp)
        return temp

    def adjust_stereo_volume_with_librosa(*_args, **_kwargs) -> None:  # pragma: no cover - stub
        return None

    audio_utils_module = SimpleNamespace(
        collect_full_audiotrack=collect_full_audiotrack,
        convert_mono_to_stereo=convert_mono_to_stereo,
        normalize_stereo_audio=normalize_stereo_audio,
        extract_acomponiment_or_vocals=extract_acomponiment_or_vocals,
        adjust_stereo_volume_with_librosa=adjust_stereo_volume_with_librosa,
    )

    def extract_audio(_video_path: str, out_path: Path) -> None:
        _touch(out_path)

    def parse_volume_intervals(_csv_path: Path) -> list:
        return []

    def create_ffmpeg_mix_video(_video_path: str, _output_ukr_audio: Path, _stereo_eng_file: Path, mix_video: Path) -> None:
        _touch(mix_video)

    ffmpeg_utils_module = SimpleNamespace(
        extract_audio=extract_audio,
        parse_volume_intervals=parse_volume_intervals,
        create_ffmpeg_mix_video=create_ffmpeg_mix_video,
    )

    return {
        "vocabulary_module": vocabulary_module,
        "subtitle_csv_module": subtitle_csv_module,
        "tts_audio_module": tts_audio_module,
        "sync_utils_module": sync_utils_module,
        "audio_utils_module": audio_utils_module,
        "ffmpeg_utils_module": ffmpeg_utils_module,
        "librosa_module": librosa_stub,
    }


def _pipeline_kwargs(tmp_path: Path) -> dict:
    subtitle = tmp_path / "sample.srt"
    subtitle.write_text("1\n00:00:00,000 --> 00:00:01,000\nhello\n")
    vocab = tmp_path / "vocab.txt"
    vocab.write_text("")
    out_dir = tmp_path / "out"
    speakers = {"default_speaker_name": "spk", "spk": {"ref_text": "", "ref_file": ""}}

    return {
        "subtitle": subtitle,
        "vocabular": vocab,
        "speakers": speakers,
        "default_speaker": speakers["spk"],
        "acomponiment_coef": 0.1,
        "voice_coef": 0.2,
        "output_folder": out_dir,
    }


def test_prepare_subtitles_creates_in_output_folder(tmp_path: Path) -> None:
    kwargs = _pipeline_kwargs(tmp_path)
    pipeline = SubtitlePipeline(**kwargs, **_make_dependencies())
    pipeline.directory.mkdir(parents=True, exist_ok=True)
    pipeline._prepare_subtitles()

    expected_directory = kwargs["output_folder"] / kwargs["subtitle"].stem
    assert pipeline.subtitle_name == "sample"
    assert pipeline.directory == expected_directory
    assert pipeline.out_path.exists()
    assert pipeline.out_path.parent == expected_directory


def test_create_video_with_english_audio_passes_output_folder(tmp_path: Path) -> None:
    kwargs = _pipeline_kwargs(tmp_path)
    dependencies = _make_dependencies()

    video = kwargs["subtitle"].with_suffix(".mp4")
    video.write_text("vid")

    records: dict[str, Path | str] = {}

    class RecordingPipeline(SubtitlePipeline):
        def run(self, video_path: str) -> None:  # pragma: no cover - stubbed pipeline
            records["directory"] = self.directory
            records["video_path"] = video_path

    SubtitlePipeline.create_video_with_english_audio(
        str(video),
        kwargs["subtitle"],
        kwargs["speakers"],
        kwargs["default_speaker"],
        kwargs["vocabular"],
        kwargs["acomponiment_coef"],
        kwargs["voice_coef"],
        kwargs["output_folder"],
        pipeline_factory=RecordingPipeline,
        pipeline_kwargs=dependencies,
    )

    expected_directory = kwargs["output_folder"] / kwargs["subtitle"].stem
    assert records["directory"] == expected_directory
    assert records["video_path"] == str(video)


def test_run_pipeline_uses_output_folder(tmp_path: Path) -> None:
    kwargs = _pipeline_kwargs(tmp_path)
    dependencies = _make_dependencies()
    pipeline = SubtitlePipeline(**kwargs, **dependencies)

    video = kwargs["subtitle"].with_suffix(".mp4")
    video.write_text("vid")

    pipeline.run(str(video))

    expected_directory = kwargs["output_folder"] / kwargs["subtitle"].stem
    assert pipeline.directory == expected_directory

    for path in [
        pipeline.out_path,
        pipeline.srt_csv_file,
        pipeline.output_csv_with_speakers,
        pipeline.output_with_preview_speeds_csv,
        pipeline.corrected_time_output_speed_csv,
        pipeline.output_audio_file,
        pipeline.stereo_eng_file,
        pipeline.out_ukr_audio,
        pipeline.acomponiment,
        pipeline.output_ukr_audio,
    ]:
        assert path.exists()
        assert path.parent == expected_directory

    assert pipeline.mix_video.exists()
    assert pipeline.mix_video.parent == kwargs["output_folder"]
