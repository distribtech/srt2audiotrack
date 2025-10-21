from __future__ import annotations

import importlib.util
from pathlib import Path

MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "srt2audiotrack-docker"
    / "whisper_service"
    / "metrics.py"
)

_spec = importlib.util.spec_from_file_location("whisper_service_metrics", MODULE_PATH)
assert _spec and _spec.loader, "Failed to load whisper_service metrics module"
metrics = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(metrics)  # type: ignore[union-attr]


def test_tokenize_strips_case():
    assert metrics.tokenize("Hello   WORLD") == ["hello", "world"]


def test_levenshtein_distance_words():
    assert metrics.levenshtein_distance(["hello", "world"], ["hello", "there", "world"]) == 1


def test_compute_metrics_extra_and_missing():
    stats = metrics.compute_metrics("hello brave world", "hello world")
    assert stats["missing"] == ["brave"]
    assert stats["extra"] == []
    assert stats["matched"] == ["hello", "world"]
    assert stats["word_error_rate"] == 1 / 3


def test_compute_metrics_with_extra_tokens():
    stats = metrics.compute_metrics("hello world", "hello there world")
    assert stats["missing"] == []
    assert stats["extra"] == ["there"]
    assert stats["matched"] == ["hello", "world"]
    assert stats["word_error_rate"] == 0.5
    assert 0 <= stats["character_error_rate"] <= 1
