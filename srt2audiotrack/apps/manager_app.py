from __future__ import annotations

import argparse
from pathlib import Path

from . import csv_app, accompaniment_app, tts_app, mix_app
from ..lock_utils import file_lock


def process(video: str | Path, subtitle: str | Path, vocabular: str | Path, output_dir: str | Path,
            language: str = "en", demucs_model: str = "mdx_extra") -> Path:
    """Full pipeline orchestrating all individual applications."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    with file_lock(video):
        csv_file = csv_app.generate_csv(subtitle, vocabular, output_dir)
        accompaniment_app.split_accompaniment(video, output_dir, demucs_model)
        tts_app.generate_audio(csv_file, output_dir, language=language)
        voice = output_dir / "tts.wav"
        acomp = output_dir / "no_vocals.wav"
        out_video = output_dir / f"{Path(video).stem}_mix{Path(video).suffix}"
        mix_app.mix_to_video(video, acomp, voice, out_video)
        return out_video


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Manage the full SRT to audio track pipeline")
    parser.add_argument("video", help="Input video file")
    parser.add_argument("subtitle", help="Subtitle SRT file")
    parser.add_argument("vocabular", help="Vocabulary file")
    parser.add_argument("output", help="Output directory")
    parser.add_argument("--language", default="en", help="Language for TTS")
    parser.add_argument("--demucs_model", default="mdx_extra", help="Demucs model name")
    args = parser.parse_args(argv)
    process(args.video, args.subtitle, args.vocabular, args.output, args.language, args.demucs_model)


if __name__ == "__main__":  # pragma: no cover - CLI entry
    main()
