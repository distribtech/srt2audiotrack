import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from srt2audiotrack.vocabulary import check_vocabular


def test_check_vocabular_creates_file(tmp_path):
    voice_dir = tmp_path / "VOICE"
    vocab_path = voice_dir / "vocabular.txt"
    # voice_dir does not exist and file missing
    result = check_vocabular(voice_dir)
    assert result == vocab_path
    assert vocab_path.exists()
    assert vocab_path.read_text() == ""
