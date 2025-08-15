# srt2audiotrack

`srt2audiotrack` is a powerful tool that automatically generates voiceovers for videos using subtitle files. It combines advanced text-to-speech synthesis with professional audio processing to create natural-sounding voice tracks while preserving the original background music and sound effects.

## Key Features
- 🎤 High-quality TTS voice generation using F5-TTS
- 🌍 Multi-language support (English and Spanish via `jpgallegoar/F5-Spanish`)
- 🎵 Intelligent audio processing with Demucs for music/speech separation
- 🎚️ Precise volume adjustment and mixing
- 🎬 Preserves original video quality
- 🚀 Batch processing support
- 🐍 Easy-to-use Python API

## Installation

### 1. Create and activate a conda environment
```bash
conda create -n srt2audio python=3.10
conda activate srt2audio
```

### 2. Install core dependencies
```bash
pip install f5-tts demucs librosa soundfile numpy ffmpeg-python
```

### 3. Install additional requirements
```bash
pip install -r requirements.txt
```

## Docker Setup

The heavy models used by this project—Whisper, Demucs and F5-TTS—are
executed inside Docker containers.  Install Docker before running the
pipeline.

### Windows
1. Install [Docker Desktop](https://www.docker.com/products/docker-desktop/).
2. Enable the WSL2 backend during installation.
3. After installation open *PowerShell* and verify:
   ```powershell
   docker version
   ```

### Linux
1. Install the Docker Engine:
   ```bash
   sudo apt update
   sudo apt install -y docker.io
   sudo systemctl enable --now docker
   ```
2. Allow your user to run Docker without `sudo`:
   ```bash
   sudo usermod -aG docker $USER
   ```
3. Log out and back in, then verify with `docker version`.

## Usage

### Command Line Interface
Process all videos in a folder with matching subtitle files:
```bash
python -m srt2audiotrack --subtitle path/to/videos --output_folder results
```

Process a single video with its subtitle:
```bash
python -m srt2audiotrack --subtitle video.srt --output_folder results
```

Generate Spanish audio using the community Spanish model:
```bash
python -m srt2audiotrack --subtitle video.srt --output_folder results --tts_language es
```

### Command Line Options
| Option | Description | Default |
|--------|-------------|---------|
| `--subtitle` | Path to folder or subtitle file | Required |
| `--videoext` | Video file extension | `.mp4` |
| `--srtext` | Subtitle file extension | `.srt` |
| `--acomponiment_coef` | Original audio mix level | `0.3` |
| `--voice_coef` | TTS voice volume level | `0.2` |
| `--output_folder` | Output directory | Same as input |
| `--tts_language` | Language for F5-TTS model (`en` or `es`) | `en` |

## How It Works

### Processing Pipeline

```
┌───────────────────────────────────────────────────────────────────────────────┐
│                                Input Files                                    │
│  ┌─────────────┐                    ┌────────────────┐                       │
│  │  video.mp4  │                    │  subtitle.srt  │                       │
│  └──────┬──────┘                    └───────┬────────┘                       │
│         │                                    │                                │
└─────────┼────────────────────────────────────┼────────────────────────────────┘
          │                                    │
          ▼                                    ▼
┌─────────────────────┐            ┌───────────────────────┐
│  1. Audio Extraction│            │ 2. Subtitle Processing│
│  • Extract audio    │            │  • Parse timestamps   │
│  • Normalize levels │            │  • Clean text         │
└─────────┬───────────┘            └──────────┬────────────┘
          │                                    │
          │                                    ▼
          │                         ┌───────────────────────┐
          │                         │ 3. Voice Generation  │
          │                         │  • TTS processing    │
          │                         │  • Apply timing      │
          │                         └──────────┬────────────┘
          │                                    │
          ▼                                    │
┌─────────────────────┐                        │
│ 4. Audio Processing │                        │
│  • Separate vocals  │◄──────────────────────┘
│  • Extract music    │
│  • Adjust levels    │
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│ 5. Final Mix        │
│  • Combine tracks   │
│  • Normalize output │
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│ 6. Video Output     │
│  • Mux with video   │
│  • Apply metadata   │
└─────────┬───────────┘
          │
          ▼
   ┌─────────────┐
   │  Output     │
   │  video.mp4  │
   └─────────────┘
```

### Audio Processing Details
1. **Input Handling**
   - Video and subtitle files are matched by name
   - Audio is extracted and normalized
   - Subtitles are parsed and cleaned

2. **Voice Generation**
   - Text is processed through F5-TTS
   - Voice clips are generated with precise timing
   - Natural pauses and intonation are preserved

3. **Audio Mixing**
   - Original audio is split into vocals and accompaniment
   - Voice tracks are mixed with background music
   - Volume levels are balanced automatically

4. **Output**
   - Final audio is mixed with original video
   - Metadata is preserved
   - Output is saved in the specified format

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
