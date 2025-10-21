# srt2audiotrack

`srt2audiotrack` builds polished, multilingual voice-over tracks from subtitle files while keeping the original mix intact. The tooling now combines text normalisation, speaker-aware F5-TTS synthesis, Whisper-based validation, Demucs source separation, and FFmpeg mastering in a resumable pipeline that can fan out across multiple workers.

## Key capabilities
- 🚀 **End-to-end pipeline** – rewrites subtitles, enriches CSV metadata, synthesises aligned narration, balances the mix, and renders a muxed video output. Every stage only runs when its artefact is missing so interrupted jobs pick up where they left off.【F:srt2audiotrack/pipeline.py†L210-L335】
- 🗣️ **Speaker-aware synthesis** – per-speaker reference audio, transcripts, and speed curves drive F5-TTS segment generation; any missing `speeds.csv` files are generated automatically.【F:srt2audiotrack/subtitle_csv.py†L162-L214】
- ✅ **Automatic quality checks** – generated speech is round-tripped through Whisper to confirm it matches the subtitle text. Mismatches are logged with similarity scores for manual review.【F:srt2audiotrack/tts_audio.py†L233-L305】
- 📦 **Job manifests & cooperative locking** – manifests expand into ordered subtitle queues and per-job lock files prevent duplicate processing across workers, with automatic stale-lock recovery.【F:srt2audiotrack/cli.py†L26-L181】【F:srt2audiotrack/pipeline.py†L25-L361】

## Architecture at a glance

1. **Subtitle normalisation** – applies vocabulary substitutions and writes `_0_mod.srt`.【F:srt2audiotrack/pipeline.py†L246-L254】【F:srt2audiotrack/vocabulary.py†L5-L76】
2. **CSV enrichment & speakers** – converts SRT to CSV, injects speaker columns, and assigns TTS speeds from speaker metadata.【F:srt2audiotrack/pipeline.py†L254-L276】【F:srt2audiotrack/subtitle_csv.py†L58-L199】
3. **Segment synthesis & validation** – F5-TTS renders per-line audio, regenerating segments that are too short and flagging Whisper mismatches for audit spreadsheets.【F:srt2audiotrack/tts_audio.py†L200-L307】【F:srt2audiotrack/subtitle_csv.py†L218-L238】
4. **Timing correction & stitching** – fixes CSV end-times from the generated waveforms and concatenates the mono narration into a full FLAC track before upmixing to stereo.【F:srt2audiotrack/pipeline.py†L278-L293】【F:srt2audiotrack/sync_utils.py†L8-L52】【F:srt2audiotrack/audio_utils.py†L83-L198】
5. **Source separation & mixing** – extracts the original soundtrack, prepares a normalised accompaniment, applies interval-based gain curves, and muxes everything back with FFmpeg.【F:srt2audiotrack/pipeline.py†L295-L333】【F:srt2audiotrack/audio_utils.py†L24-L250】【F:srt2audiotrack/ffmpeg_utils.py†L1-L89】

```
┌────────────────────┐   ┌────────────────────┐   ┌────────────────────────┐
│ Subtitle           │   │ CSV & speaker      │   │ Timing correction &     │
│ normalisation      │──▶│ enrichment         │──▶│ narration stitching     │
└────────────────────┘   └────────────────────┘   └────────────────────────┘
              │                       │                          │
              ▼                       ▼                          ▼
       Vocabulary rules        Speaker metadata           FLAC narration
              │                       │                          │
              └────────────┬──────────┴──────────────┬───────────┘
                           ▼                         ▼
                   ┌────────────────────┐   ┌────────────────────┐
                   │ Source audio prep  │   │ Dynamic mixing &   │
                   │ (demucs, loudness) │──▶│ final muxing       │
                   └────────────────────┘   └────────────────────┘
```

## Installation
1. Create and activate an environment (example using conda):
   ```bash
   conda create -n srt2audio python=3.10
   conda activate srt2audio
   ```
2. Install the core runtime dependencies:
   ```bash
   pip install f5-tts demucs librosa soundfile numpy ffmpeg-python
   ```
3. Install the project requirements (includes Whisper, Demucs, F5-TTS, FastAPI, etc.):
   ```bash
   pip install -r requirements.txt
   ```
4. Ensure `ffmpeg` is available on your `PATH` for muxing and loudness normalisation.

## Preparing the `VOICE` library
Each subtitle/video set should contain a neighbouring `VOICE/` directory with:
- Reference `.wav` files for each speaker (the first one becomes the default).【F:srt2audiotrack/subtitle_csv.py†L162-L194】
- Matching `.txt` transcripts so synthesis can validate reference text.【F:srt2audiotrack/subtitle_csv.py†L195-L203】
- Optional `speeds.csv` envelopes per speaker; missing files are generated automatically using the F5-TTS helper.【F:srt2audiotrack/subtitle_csv.py†L200-L214】
- A shared `vocabular.txt` file; it is created on demand if absent.【F:srt2audiotrack/vocabulary.py†L5-L13】

See `tests/one_voice` for a minimal layout.

## Usage
### Quick start
Process every `.srt` file in a directory, producing muxed videos beside the originals:
```bash
python -m srt2audiotrack --subtitle path/to/records
```
Process a single subtitle/video pair:
```bash
python -m srt2audiotrack --subtitle path/to/video.srt
```

### Working with manifests and multiple workers
- Use `--job-manifest-dir` to point at newline-delimited job files; relative paths are resolved next to the manifest and duplicates are automatically removed.【F:srt2audiotrack/cli.py†L26-L143】
- Provide `--worker-id` (or rely on the hostname) so lock files record who owns a job. Locks refresh on a heartbeat and are reclaimed when stale, enabling safe restarts across machines.【F:srt2audiotrack/cli.py†L77-L181】【F:srt2audiotrack/pipeline.py†L25-L361】

### Output structure and resume behaviour
For a subtitle named `example.srt`, intermediate files live under `OUTPUT/example/` while the final muxed video is written beside the subtitle (or into `--output_folder`). The pipeline checks for each artefact before running a step, so reruns process only the missing stages.【F:srt2audiotrack/pipeline.py†L171-L335】

### Command line options
| Option | Description | Default |
|--------|-------------|---------|
| `--subtitle` | Path to subtitle file or directory to scan | `records` |
| `--speeds` | Path to default speeds table | `speeds.csv` |
| `--delay` | Minimum gap used when collapsing subtitle lines | `0.00001` |
| `--voice` | Reference voice file used for diagnostics | `basic_ref_en.wav` |
| `--text` | Reference text used with `--voice` | `some call me nature, others call me mother nature.` |
| `--videoext` | Expected video extension when scanning folders | `.mp4` |
| `--srtext` | Subtitle extension when scanning folders | `.srt` |
| `--outfileending` | Suffix for rendered video names | `_out_mix.mp4` |
| `--vocabular` | Override path to vocabulary file | `vocabular.txt` |
| `--config` / `-c` | Optional TOML configuration file | `basic.toml` |
| `--acomponiment_coef` | Mix level for the background accompaniment | `0.2` |
| `--voice_coef` | Mix level for generated voice | `0.2` |
| `--output_folder` | Custom directory for pipeline artefacts and final video | same as subtitle parent |
| `--job-manifest-dir` | Folder containing job manifest files | *(empty)* |
| `--worker-id` | Identifier recorded in lock files | hostname or `PIPELINE_WORKER_ID` |
| `--lock-timeout` | Seconds before a lock is considered stale | `1800.0` |
| `--lock-heartbeat` | Seconds between lock refreshes | `60.0` |

(See `python -m srt2audiotrack --help` for the authoritative list.)【F:srt2audiotrack/cli.py†L44-L181】

## Development & testing
- Run the Python unit tests:
  ```bash
  pytest tests/unit
  ```
- Sample subtitle fixtures live in `tests/one_voice` and `tests/multi_voice`.
- The `tests/test_whisper_metrics.py` script exercises the Whisper validation pipeline.

## Microservice-based demo (Docker)

The repository ships with a microservice-oriented demo web application under `srt2audiotrack-docker/`. The compose stack splits the responsibilities across four containers:

| Service | Role | Exposed port | Notes |
|---------|------|--------------|-------|
| `tts_service` | Generates mock narration audio from plain text. | `8001` | Coordinates synthesis with a `.lock` file. |
| `demucs_service` | Performs a lightweight Demucs-style source separation. | `8002` | Uses a `.lock` for its workspace. |
| `subtitles_service` | Stores subtitle vocabulary in a SQLite database. | `8003` | Uses a `.lock` for SQLite writes. |
| `orchestrator` | Web UI that orchestrates the three backend services. | `8000` | HTTP frontend for the services. |

### Prerequisites

- Docker Engine 20.10+
- Docker Compose v2 (`docker compose` CLI)

### Building the images

```bash
cd srt2audiotrack-docker
docker compose build
# or refresh the base images first
docker compose build --pull
```

### Running the stack

```bash
cd srt2audiotrack-docker
docker compose up
# Run in detached mode once you are happy with the logs:
docker compose up -d
```

The orchestrator UI becomes available at <http://localhost:8000>. Submit text (and optional subtitle snippets) to exercise the round-trip across the TTS, Demucs, and subtitle vocabulary services. Named volumes persist generated audio and the SQLite database between runs.

To stop the stack and remove containers, run:

```bash
docker compose down
```

### Using the Docker images elsewhere

All services expose a FastAPI app on the ports listed above. Once built, you can reuse the images in other compose files or orchestration platforms. For example:

```bash
docker run --rm -p 9000:8001 tts_service
docker run --rm -p 9001:8002 demucs_service
docker run --rm -p 9002:8003 subtitles_service
docker run --rm -p 9003:8000 \
  -e TTS_URL=http://host.docker.internal:9000 \
  -e DEMUCS_URL=http://host.docker.internal:9001 \
  -e SUBTITLES_URL=http://host.docker.internal:9002 \
  orchestrator
```

With the containers running, the CLI module remains available in parallel for offline batch conversion.

### Working with `.lock` files

- **Inspection** – Lock files live beside the subtitle output directory (e.g. `OUTPUT/example/example.lock`). They are plain text and record the current worker ID, timestamps, and heartbeat interval.
- **Refreshing** – Active workers refresh their lock on a background heartbeat. If a worker stops unexpectedly the lock becomes stale after `--lock-timeout` seconds and other workers automatically reclaim the job.【F:srt2audiotrack/pipeline.py†L25-L144】
- **Manual recovery** – When coordinating manually, you can delete or rename a stale lock file if you are sure no other worker is operating on the job. On the next manifest scan, an available worker obtains a fresh lock and resumes from cached artefacts.

## Python API
Use the high-level helper to invoke the pipeline programmatically:
```python
from pathlib import Path
from srt2audiotrack import SubtitlePipeline

SubtitlePipeline.create_video_with_english_audio(
    video_path="video.mp4",
    subtitle=Path("subtitles.srt"),
    speakers=speakers_config,
    default_speaker=speakers_config["en"],
    vocabular=Path("VOICE/vocabular.txt"),
    acomponiment_coef=0.3,
    voice_coef=0.2,
    output_folder=Path("out"),
)
```
This wrapper wires up the same pipeline used by the CLI while allowing advanced dependency injection for testing.【F:srt2audiotrack/pipeline.py†L372-L403】

## Troubleshooting
- Verify the external CLIs are available:
  ```bash
  python -m whisper --help
  python -m demucs.separate --help
  python -m f5_tts.cli --help
  ```
- If a job is skipped with a lock warning, inspect the `.lock` file inside the subtitle output folder to confirm the active worker ID or delete stale locks after the timeout has elapsed.【F:srt2audiotrack/pipeline.py†L25-L361】

Happy dubbing!
