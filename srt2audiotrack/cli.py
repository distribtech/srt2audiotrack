import argparse
import os
import socket
from pathlib import Path
from typing import Iterable

from .subtitle_csv import get_speakers_from_folder, check_texts, check_speeds_csv
from .vocabulary import check_vocabular
from .pipeline import SubtitlePipeline, ActivePipelineLockError


def _default_worker_id() -> str:
    return os.environ.get("PIPELINE_WORKER_ID") or socket.gethostname()


def _deduplicate_preserve_order(items: Iterable[Path]) -> list[Path]:
    seen: set[Path] = set()
    ordered: list[Path] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            ordered.append(item)
    return ordered


def load_jobs_from_manifest(manifest_dir: Path) -> list[Path]:
    jobs: list[Path] = []
    if not manifest_dir.exists():
        raise FileNotFoundError(f"Job manifest directory not found: {manifest_dir}")
    for manifest_file in sorted(manifest_dir.glob("*")):
        if not manifest_file.is_file():
            continue
        for raw_line in manifest_file.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            path = Path(line)
            if not path.is_absolute():
                path = manifest_file.parent / path
            jobs.append(path)
    return _deduplicate_preserve_order(jobs)


def main():
    # Initialize the argument parser
    parser = argparse.ArgumentParser(description="Script that processes a subtitle file")

    # Add a folder argument
    parser.add_argument('--subtitle', type=str, help="Path to the subtitle folder/file to be processed",
                        default=r"records")
    # Add default tts speeds file
    parser.add_argument('--speeds', type=str, help="Path to the speeds of tts",
                        default="speeds.csv")
    # Add delay to think that must be only one sentences, default value very very low
    parser.add_argument('--delay', type=float, help="Delay to think that must be only one sentences",
                        default=0.00001) 
    # Add voice
    parser.add_argument('--voice', type=str, help="Path to voice", default="basic_ref_en.wav")
    # Add text
    parser.add_argument('--text', type=str, help="Path to text for voice", default="some call me nature, others call me mother nature.")
    # Add video extension
    parser.add_argument('--videoext', type=str, help="Video extension of video files", default=".mp4")
    # Add subtitles extension
    parser.add_argument('--srtext', type=str, help="Subtitle extension of files", default=".srt")
    # Add out video ending
    parser.add_argument('--outfileending', type=str, help="Out video file ending", default="_out_mix.mp4")
    # Add vocabular
    parser.add_argument('--vocabular', type=str, help="Vocabular of transcriptions", default="vocabular.txt")
    # Add config
    parser.add_argument('--config', "-c", type=str, help="Config file", default="basic.toml")
    # Add acomponiment coeficient
    parser.add_argument('--acomponiment_coef', type=float, help="Acomponiment coeficient", default=0.2)
    # Add voice coeficient
    parser.add_argument('--voice_coef', type=float, help="Voice coeficient", default=0.2)
    # Add output folder
    parser.add_argument('--output_folder', type=str, help="Output folder", default="")
    # Job manifest and coordination options
    parser.add_argument(
        '--job-manifest-dir',
        type=str,
        help="Directory containing job manifest files (one subtitle path per line)",
        default="",
    )
    parser.add_argument(
        '--worker-id',
        type=str,
        help="Identifier written to pipeline lock files",
        default="",
    )
    parser.add_argument(
        '--lock-timeout',
        type=float,
        help="Seconds before a pipeline lock is considered stale",
        default=1800.0,
    )
    parser.add_argument(
        '--lock-heartbeat',
        type=float,
        help="Seconds between lock heartbeat updates",
        default=60.0,
    )

    # Parse the arguments
    args = parser.parse_args()

    # Extract the folder argument
    subtitle = args.subtitle
    speeds = args.speeds
    delay = args.delay
    voice = args.voice
    text = args.text
    videoext = args.videoext
    srtext = args.srtext
    outfileending = args.outfileending
    vocabular = args.vocabular
    acomponiment_coef = args.acomponiment_coef
    voice_coef = args.voice_coef
    output_folder = args.output_folder #It must be done in future. Now output file in the same directory than input file
    job_manifest_dir = Path(args.job_manifest_dir) if args.job_manifest_dir else None
    worker_id = args.worker_id or _default_worker_id()
    lock_timeout = args.lock_timeout
    heartbeat_interval = args.lock_heartbeat

    print(f"Processing folder: {subtitle}")

    voice_dir = Path(subtitle)/"VOICE"

    vocabular_pth = check_vocabular(voice_dir)
    check_texts(voice_dir)
    check_speeds_csv(voice_dir)

    speakers = get_speakers_from_folder(voice_dir)
    if not speakers:
        print("I need at least one speaker.")
        exit(1)
    default_speaker = speakers.get(speakers["default_speaker_name"])

    if job_manifest_dir:
        sbt_paths = load_jobs_from_manifest(job_manifest_dir)
    else:
        sbt_paths = [
            Path(p)
            for p in SubtitlePipeline.list_subtitle_files(
                subtitle, srtext, exclude_ext="_0_mod.srt"
            )
        ]
        if Path(subtitle).is_file():
            sbt_paths = [Path(subtitle)]

    for subtitle in sbt_paths:
        video_path = subtitle.with_suffix(videoext)
        ready_video_file_name = subtitle.stem + "_out_mix.mp4"
        ready_video_path = video_path.parent / ready_video_file_name
        if video_path.is_file() and not ready_video_path.is_file():
            pipeline = SubtitlePipeline(
                subtitle,
                vocabular_pth,
                speakers,
                default_speaker,
                acomponiment_coef,
                voice_coef,
                output_folder,
            )
            if SubtitlePipeline.cleanup_stale_lock(pipeline.directory, lock_timeout):
                print(f"Recovered stale lock for {subtitle}. Re-claiming job.")
            try:
                pipeline.run(
                    video_path,
                    worker_id=worker_id,
                    heartbeat_interval=heartbeat_interval,
                    lock_timeout=lock_timeout,
                )
            except ActivePipelineLockError:
                print(
                    f"Lock already active for {subtitle}. Skipping job for worker {worker_id}."
                )



if __name__ == "__main__":
    main()


