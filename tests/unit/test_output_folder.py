from pathlib import Path
import sys
import os
import types

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import vocabulary
for name in ['subtitle_csv', 'tts_audio', 'sync_utils', 'ffmpeg_utils']:
    sys.modules[name] = types.ModuleType(name)

audio_stub = types.ModuleType('audio_utils')
def _stub(*args, **kwargs):
    pass
audio_stub.convert_mono_to_stereo = _stub
audio_stub.normalize_stereo_audio = _stub
audio_stub.extract_acomponiment_or_vocals = _stub
audio_stub.adjust_stereo_volume_with_librosa = _stub
sys.modules['audio_utils'] = audio_stub
sys.modules['vocabulary'] = vocabulary

import pipeline

def test_prepare_subtitles_creates_in_output_folder(tmp_path):
    subtitle = tmp_path / "sample.srt"
    subtitle.write_text("1\n00:00:00,000 --> 00:00:01,000\nhello\n")
    vocab = tmp_path / "vocab.txt"
    vocab.write_text("")
    out_dir = tmp_path / "out"

    sp = pipeline.SubtitlePipeline(
        subtitle,
        vocab,
        {},
        {},
        0.0,
        0.0,
        out_dir,
    )

    directory, name, out_path = sp.prepare_subtitles()

    assert name == "sample"
    assert directory == out_dir / "sample"
    assert out_path.exists()
    assert out_path.parent == directory

def test_create_video_with_english_audio_passes_output_folder(tmp_path, monkeypatch):
    video = tmp_path / "video.mp4"
    video.write_text("vid")
    subtitle = tmp_path / "sample.srt"
    subtitle.write_text("1\n00:00:00,000 --> 00:00:01,000\nhello\n")
    vocab = tmp_path / "vocab.txt"
    vocab.write_text("")
    speakers = {"default_speaker_name": "spk", "spk": {"ref_text": "", "ref_file": ""}}
    default_speaker = speakers["spk"]
    out_dir = tmp_path / "out"

    calls = {}

    def fake_subtitles_to_audio(self):
        calls["subdir"] = self.directory
        self.srt_csv_file = Path("dummy.csv")
        self.stereo_eng_file = Path("dummy.wav")
        return self.srt_csv_file, self.stereo_eng_file

    def fake_process_video_file(self, video_path_arg):
        calls["procdir"] = self.directory

    monkeypatch.setattr(
        pipeline.SubtitlePipeline, "subtitles_to_audio", fake_subtitles_to_audio
    )
    monkeypatch.setattr(
        pipeline.SubtitlePipeline, "process_video_file", fake_process_video_file
    )

    pipeline.SubtitlePipeline.create_video_with_english_audio(
        str(video),
        subtitle,
        speakers,
        default_speaker,
        vocab,
        0.1,
        0.2,
        out_dir,
    )

    expected = out_dir / subtitle.stem
    assert calls["subdir"] == expected
    assert calls["procdir"] == expected


def test_subtitle_pipeline_run_uses_output_folder(tmp_path, monkeypatch):
    video = tmp_path / "video.mp4"
    video.write_text("vid")
    subtitle = tmp_path / "sample.srt"
    subtitle.write_text("1\n00:00:00,000 --> 00:00:01,000\nhello\n")
    vocab = tmp_path / "vocab.txt"
    vocab.write_text("")
    speakers = {"default_speaker_name": "spk", "spk": {"ref_text": "", "ref_file": ""}}
    default_speaker = speakers["spk"]
    out_dir = tmp_path / "out"

    calls = {}

    def fake_prepare_subtitles(self):
        calls["prep"] = self.output_folder / self.subtitle.stem
        self.directory = calls["prep"]
        self.subtitle_name = self.subtitle.stem
        self.out_path = Path("dummy.srt")
        return self.directory, self.subtitle_name, self.out_path

    def fake_subtitles_to_audio(self):
        calls["audio"] = self.directory
        self.srt_csv_file = Path("dummy.csv")
        self.stereo_eng_file = Path("dummy.wav")
        return self.srt_csv_file, self.stereo_eng_file

    def fake_process_video_file(self, video_path_arg):
        calls["video"] = self.directory

    monkeypatch.setattr(
        pipeline.SubtitlePipeline, "prepare_subtitles", fake_prepare_subtitles
    )
    monkeypatch.setattr(
        pipeline.SubtitlePipeline, "subtitles_to_audio", fake_subtitles_to_audio
    )
    monkeypatch.setattr(
        pipeline.SubtitlePipeline, "process_video_file", fake_process_video_file
    )

    sp = pipeline.SubtitlePipeline(
        subtitle,
        vocab,
        speakers,
        default_speaker,
        0.1,
        0.2,
        out_dir,
    )

    sp.run(str(video))

    expected = out_dir / subtitle.stem
    assert calls["prep"] == expected
    assert calls["audio"] == expected
    assert calls["video"] == expected
