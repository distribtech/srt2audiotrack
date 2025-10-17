from pathlib import Path
import os
import sys
import types

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

librosa_stub = types.ModuleType("librosa")
librosa_stub.get_samplerate = lambda *_args, **_kwargs: 1
librosa_stub.load = lambda *_args, **kwargs: ([0.0], kwargs.get("sr", 1))
librosa_stub.resample = lambda data, orig_sr, target_sr: data
sys.modules["librosa"] = librosa_stub

for name in ["subtitle_csv", "tts_audio", "sync_utils", "ffmpeg_utils", "audio_utils"]:
    sys.modules[f"srt2audiotrack.{name}"] = types.ModuleType(name)

audio_stub = sys.modules["srt2audiotrack.audio_utils"]


def _stub(*_args, **_kwargs):
    pass


audio_stub.convert_mono_to_stereo = _stub
audio_stub.normalize_stereo_audio = _stub
audio_stub.extract_acomponiment_or_vocals = _stub
audio_stub.adjust_stereo_volume_with_librosa = _stub

from srt2audiotrack.pipeline import SubtitlePipeline


def _make_pipeline(tmp_path: Path) -> SubtitlePipeline:
    subtitle = tmp_path / "sample.srt"
    subtitle.write_text("1\n00:00:00,000 --> 00:00:01,000\nhello\n")
    vocab = tmp_path / "vocab.txt"
    vocab.write_text("")
    out_dir = tmp_path / "out"
    speakers = {"default_speaker_name": "spk", "spk": {"ref_text": "", "ref_file": ""}}
    default_speaker = speakers["spk"]

    return SubtitlePipeline(
        subtitle=subtitle,
        vocabular=vocab,
        speakers=speakers,
        default_speaker=default_speaker,
        acomponiment_coef=0.1,
        voice_coef=0.2,
        output_folder=out_dir,
    )


def test_prepare_subtitles_creates_in_output_folder(tmp_path):
    pipeline = _make_pipeline(tmp_path)
    pipeline.directory.mkdir(parents=True, exist_ok=True)
    pipeline._prepare_subtitles()

    assert pipeline.subtitle_name == "sample"
    assert pipeline.directory == pipeline.output_folder / "sample"
    assert pipeline.out_path.exists()
    assert pipeline.out_path.parent == pipeline.directory


def test_create_video_with_english_audio_passes_output_folder(tmp_path, monkeypatch):
    pipeline_instance = _make_pipeline(tmp_path)
    video = pipeline_instance.subtitle.with_suffix(".mp4")
    video.write_text("vid")

    calls: dict[str, Path | str] = {}

    def fake_run(self, video_path: str) -> None:
        calls["directory"] = self.directory
        calls["video_path"] = video_path

    monkeypatch.setattr(SubtitlePipeline, "run", fake_run)

    SubtitlePipeline.create_video_with_english_audio(
        str(video),
        pipeline_instance.subtitle,
        pipeline_instance.speakers,
        pipeline_instance.default_speaker,
        pipeline_instance.vocabular,
        pipeline_instance.acomponiment_coef,
        pipeline_instance.voice_coef,
        pipeline_instance.output_folder,
    )

    expected_directory = pipeline_instance.output_folder / pipeline_instance.subtitle.stem
    assert calls["directory"] == expected_directory
    assert calls["video_path"] == str(video)


def test_run_pipeline_uses_output_folder(tmp_path, monkeypatch):
    pipeline = _make_pipeline(tmp_path)
    video = pipeline.subtitle.with_suffix(".mp4")
    video.write_text("vid")

    calls: dict[str, Path] = {}

    def fake_prepare(self) -> None:
        calls["prep"] = self.directory

    def fake_convert(self) -> None:
        calls["audio"] = self.directory

    def fake_process(self, video_path: str) -> None:
        calls["video"] = self.directory

    monkeypatch.setattr(SubtitlePipeline, "_prepare_subtitles", fake_prepare)
    monkeypatch.setattr(SubtitlePipeline, "_convert_subs_to_audio", fake_convert)
    monkeypatch.setattr(SubtitlePipeline, "process_video_file", fake_process)

    pipeline.run(str(video))

    expected = pipeline.output_folder / pipeline.subtitle.stem
    assert calls["prep"] == expected
    assert calls["audio"] == expected
    assert calls["video"] == expected
