# srt2audiotrack

`srt2audiotrack` creates polished, multilingual voice-over tracks from subtitle files while keeping the original mix intact. It combines text normalisation, high-quality TTS synthesis, intelligent mixing, and FFmpeg-based mastering into a resumable pipeline that can be orchestrated across multiple workers.

## Key capabilities
- 🚀 **End-to-end pipeline** – automatically rewrites subtitles, generates aligned speech, balances against the original soundtrack, and delivers a muxed video output. 【F:srt2audiotrack/pipeline.py†L185-L333】
- 🗣️ **Speaker-aware synthesis** – supports multiple reference voices with per-speaker speed curves derived from `speeds.csv` metadata. Missing curves are generated on-demand. 【F:srt2audiotrack/subtitle_csv.py†L137-L213】
- 🧰 **Resumable by design** – every processing stage caches its artefacts so that interrupted runs simply pick up where they left off. 【F:srt2audiotrack/pipeline.py†L246-L333】
- 📦 **Job manifests & locking** – optional manifest files let you queue work for farms of machines while cooperative lock files prevent duplicate processing. 【F:srt2audiotrack/cli.py†L77-L176】【F:srt2audiotrack/pipeline.py†L33-L361】

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
3. Install the project requirements:
   ```bash
   pip install -r requirements.txt
   ```
4. Ensure `ffmpeg` is available on your `PATH` for muxing and loudness normalisation.

## Preparing the `VOICE` library
The CLI expects a `VOICE` subfolder alongside each subtitle/video set. Populate it with:
- Reference `.wav` files for each speaker. 【F:srt2audiotrack/subtitle_csv.py†L162-L194】
- Matching `.txt` transcripts so the tool can validate training text. 【F:srt2audiotrack/subtitle_csv.py†L196-L203】
- Optional `speeds.csv` curves stored under a folder named after the speaker (generated automatically if missing). 【F:srt2audiotrack/subtitle_csv.py†L177-L213】
- A shared `vocabular.txt` file for search/replace rules; it will be created if absent. 【F:srt2audiotrack/vocabulary.py†L5-L13】

See `tests/one_voice` for an example directory layout.

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
- Use `--job-manifest-dir` to point to a directory containing plain-text job lists (one subtitle path per line, comments allowed). Duplicate paths are deduplicated automatically. 【F:srt2audiotrack/cli.py†L26-L41】【F:srt2audiotrack/cli.py†L77-L140】
- Provide `--worker-id` (or rely on the hostname) so lock files record who owns a job. Locks refresh on a heartbeat and are reclaimed when stale, enabling safe restarts across machines. 【F:srt2audiotrack/cli.py†L85-L122】【F:srt2audiotrack/pipeline.py†L210-L361】

### Output structure and resume behaviour
For a subtitle named `example.srt`, intermediate files live under `OUTPUT/example/` while the final muxed video is written beside the subtitle (or into `--output_folder`). 【F:srt2audiotrack/pipeline.py†L171-L333】 The pipeline skips any step whose artefact already exists, so reruns only process missing stages.

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

(See `python -m srt2audiotrack --help` for the authoritative list.) 【F:srt2audiotrack/cli.py†L44-L123】

## What the pipeline does
1. **Subtitle normalisation** – applies vocabulary replacements and prepares `_0_mod.srt`. 【F:srt2audiotrack/pipeline.py†L246-L254】
2. **CSV enrichment** – adds speaker assignments and speed hints before triggering TTS generation. 【F:srt2audiotrack/pipeline.py†L254-L276】
3. **Timing corrections & stitching** – fixes end times and builds a full FLAC narration track. 【F:srt2audiotrack/pipeline.py†L278-L293】
4. **Source audio prep** – extracts and separates the original soundtrack, resampling and normalising the accompaniment. 【F:srt2audiotrack/pipeline.py†L295-L309】【F:srt2audiotrack/audio_utils.py†L24-L99】
5. **Dynamic mixing** – applies interval-based volume shaping before muxing with FFmpeg. 【F:srt2audiotrack/pipeline.py†L311-L333】【F:srt2audiotrack/ffmpeg_utils.py†L1-L52】

## Scheme of work

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

## Multi-application orchestration

The pipeline coordinates several cooperating processes and external tools. The following
ASCII sketch shows how manifests, workers, and helper applications interact when processing
jobs in parallel:

```
┌──────────────────────────┐        ┌──────────────────────────┐
│ Manifest directory       │  fan   │   Worker processes       │
│ (*.txt job lists)        │──out──▶│ (CLI invocations, one    │
└──────────────────────────┘        │  per machine/container)   │
        ▲                           └──────────────────────────┘
        │                                   │
        │ reload manifests                  │ acquire lock per job
        │                                   ▼
┌──────────────────────────┐        ┌──────────────────────────┐
│ Lock files (*.lock)      │◀──────▶│ Pipeline coordinator     │
│ (ownership + heartbeat)  │        │ (Python pipeline stages) │
└──────────────────────────┘        └──────────────────────────┘
                                            │
                                            │ dispatches work units
                                            ▼
       ┌─────────────┬─────────────┬──────────────┬──────────────┐
       │ Vocabulary  │ TTS engine  │ Demucs/FFmpeg│ Mixdown/FFmpeg│
       │ management  │ (f5-tts)    │ separation   │ mux & export  │
       └─────────────┴─────────────┴──────────────┴──────────────┘
```

Each worker watches the manifest directory and claims available jobs by touching or updating
the corresponding `.lock` file. The lock stores the worker ID and heartbeat timestamps so
that other workers can safely skip in-progress work or reclaim stale jobs. The pipeline
continues through the normalisation, synthesis, separation, and muxing stages, delegating
to specialised apps such as `demucs` and `ffmpeg` where needed.

### Working with `.lock` files

- **Inspection** – Lock files live beside the subtitle output directory (e.g.
  `OUTPUT/example/example.lock`). They are plain text and can be opened to check the
  current owner, timestamps, and heartbeat interval.
- **Refreshing** – Active workers refresh their lock on a background heartbeat. If a
  worker is terminated unexpectedly, the lock becomes stale after `--lock-timeout`
  seconds and other workers will automatically reclaim the job.
- **Manual recovery** – When coordinating manually, you can delete a stale lock file if
  you are certain no other worker is operating on the job. Upon the next manifest scan,
  an available worker will obtain a fresh lock and resume from cached artefacts.

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
This wrapper wires up the same pipeline used by the CLI while allowing advanced dependency injection for testing. 【F:srt2audiotrack/pipeline.py†L372-L403】

## Troubleshooting
- Verify the external CLIs are available:
  ```bash
  python -m whisper --help
  python -m demucs.separate --help
  python -m f5_tts.cli --help
  ```
- If a job is skipped with a lock warning, inspect the `.lock` file inside the subtitle output folder to confirm the active worker ID or delete stale locks after the timeout has elapsed. 【F:srt2audiotrack/pipeline.py†L33-L361】

Happy dubbing!
