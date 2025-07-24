import tempfile
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from vocabular import modify_subtitles_with_vocabular_wholefile


def test_whole_word_replacement_only_in_text():
    srt_content = """1
00:00:00,000 --> 00:00:01,000
hello cat world

2
00:00:01,500 --> 00:00:02,000
scattered catacombs
"""
    vocab_content = "cat<=>dog"

    with tempfile.TemporaryDirectory() as tmpdir:
        srt_path = Path(tmpdir) / "in.srt"
        vocab_path = Path(tmpdir) / "vocab.txt"
        out_path = Path(tmpdir) / "out.srt"
        srt_path.write_text(srt_content, encoding="utf-8")
        vocab_path.write_text(vocab_content, encoding="utf-8")

        modify_subtitles_with_vocabular_wholefile(srt_path, vocab_path, out_path)
        result = out_path.read_text(encoding="utf-8")

    expected = """1
00:00:00,000 --> 00:00:01,000
hello Dog world

2
00:00:01,500 --> 00:00:02,000
scattered catacombs
"""
    assert result == expected
