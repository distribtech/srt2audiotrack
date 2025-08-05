# srt2audiotrack

`srt2audiotrack` converts videos with subtitle files into new videos with an automatically generated English audio track. The pipeline uses **F5‑TTS** for text‑to‑speech generation and FFmpeg for audio mixing.

## Installation

### 1. Create an environment (Windows example)
```bash
conda create -n f5-tts-demucs python=3.10
conda activate f5-tts-demucs
```

### 2. Install dependencies
- Install [F5‑TTS](https://github.com/SWivid/F5-TTS):
  ```bash
  pip install f5-tts
  ```
- Install [Demucs](https://github.com/adefossez/demucs) for accompaniment extraction:
  ```bash
  python -m pip install -U demucs
  ```
- Install other Python requirements:
  ```bash
  pip install -r requirements.txt
  ```

## Usage
Run the application as a module by providing a folder that contains videos and matching `.srt` subtitle files:
```bash
python -m srt2audiotrack --subtitle records\one_voice
```
The processed videos will be saved in the folder specified by `--output_folder`
(or next to the subtitles if not provided) with the suffix `_out_mix.mp4`.

### Command line options
- `--subtitle` – path to a folder or a single subtitle file.
- `--videoext` – extension of the video files (default: `.mp4`).
- `--srtext` – extension of subtitle files (default: `.srt`).
- `--acomponiment_coef` – mix coefficient for the original audio (default: `0.3`).
- `--voice_coef` – proportion of generated voice in the final mix (default: `0.2`).
- `--output_folder` – directory where all intermediate and result files will be stored.

Run `python -m srt2audiotrack -h` to see all available options.

## Pipeline Overview

```
Input Files:
  video.mp4
  subtitles.srt

  ┌─────────────────┐     ┌─────────────────┐     ┌──────────────────────┐
  │ 1. Extract      │     │ 2. Generate     │     │ 3. Process           │
  │    Audio        │────▶│    TTS Audio    │────▶│    Audio Mix        │
  └─────────────────┘     └─────────────────┘     │   ┌──────────────┐   │
                                                  │   │  Original    │   │
  ┌─────────────────┐     ┌─────────────────┐     │   │  Video       │   │
  │ 4. Separate     │     │ 5. Adjust       │     │   └──────┬───────┘   │
  │    Vocals       │────▶│    Volume       │────▶│           │           │
  └─────────────────┘     └─────────────────┘     │   ┌──────▼───────┐   │
                                                  │   │  TTS Voice   │   │
  ┌─────────────────┐     ┌─────────────────┐     │   │              │   │
  │ 6. Extract      │     │ 7. Mix          │     │   └──────┬───────┘   │
  │    Accompaniment│────▶│    Audio        │────▶│           │           │
  └─────────────────┘     └─────────────────┘     │   ┌──────▼───────┐   │
                                                  │   │  Accompaniment│   │
                                                  │   │  (Music/SFX)  │   │
                                                  │   └──────┬───────┘   │
                                                  │          │           │
                                                  └──────────┼───────────┘
                                                           │
                                                      ┌─────▼────┐
                                                      │  Output  │
                                                      │  Video   │
                                                      └──────────┘
```

### Using as a module
The library exposes a functional API that can be used directly in web
applications. Only a few paths and speaker settings are required:

```python
from pathlib import Path
from srt2audiotrack import create_video_with_english_audio

create_video_with_english_audio(
    "video.mp4",
    Path("subtitles.srt"),
    speakers,
    default_speaker,
    Path("vocabular.txt"),
    acomponiment_coef=0.3,
    voice_coef=0.2,
    output_folder=Path("out"),
)
```

An example React GUI that works with this module is available in the `sub-edit` folder.

## Notes
The `VOICE` subfolder should contain reference speaker audio files together with their texts and generated `speeds.csv` files. See `tests/one_voice` for an example structure.
