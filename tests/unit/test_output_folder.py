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
sys.modules['audio_utils'] = audio_stub
sys.modules['vocabulary'] = vocabulary

import pipeline

def test_prepare_subtitles_creates_in_output_folder(tmp_path):
    subtitle = tmp_path / "sample.srt"
    subtitle.write_text("1\n00:00:00,000 --> 00:00:01,000\nhello\n")
    vocab = tmp_path / "vocab.txt"
    vocab.write_text("")
    out_dir = tmp_path / "out"

    directory, name, out_path = pipeline.prepare_subtitles(subtitle, vocab, out_dir)

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
    def fake_subtitles_to_audio(directory, subtitle_name, out_path, speakers, default_speaker):
        calls["subdir"] = directory
        return Path("dummy.csv"), Path("dummy.wav")
    def fake_process_video_file(video_path_arg, directory, subtitle_name, srt_csv_file, stereo_eng_file, coef):
        calls["procdir"] = directory

    monkeypatch.setattr(pipeline, "subtitles_to_audio", fake_subtitles_to_audio)
    monkeypatch.setattr(pipeline, "process_video_file", fake_process_video_file)

    pipeline.create_video_with_english_audio(
        str(video), subtitle, speakers, default_speaker, vocab, 0.1, out_dir
    )

    expected = out_dir / subtitle.stem
    assert calls["subdir"] == expected
    assert calls["procdir"] == expected
