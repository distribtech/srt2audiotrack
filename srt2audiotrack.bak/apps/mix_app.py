from __future__ import annotations

import argparse
from pathlib import Path

from .. import ffmpeg_utils
from ..lock_utils import file_lock


def mix_to_video(video_path: str | Path, accompaniment_wav: str | Path, voice_wav: str | Path, output_path: str | Path) -> Path:
    """Combine original video with generated English audio."""
    with file_lock(video_path):
        ffmpeg_utils.create_ffmpeg_mix_video(video_path, accompaniment_wav, voice_wav, output_path)
        return Path(output_path)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Mix audio tracks into a video")
    parser.add_argument("video", help="Input video file")
    parser.add_argument("acompaniment", help="Background accompaniment track")
    parser.add_argument("voice", help="Generated voice track")
    parser.add_argument("output", help="Path to mixed video")
    args = parser.parse_args(argv)
    mix_to_video(args.video, args.acompaniment, args.voice, args.output)


if __name__ == "__main__":  # pragma: no cover - CLI entry
    main()
