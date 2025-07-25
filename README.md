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
Run the main script by providing a folder that contains videos and matching `.srt` subtitle files:
```bash
python main.py --subtitle records\one_voice
```
The processed videos will be saved in the folder specified by `--output_folder`
(or next to the subtitles if not provided) with the suffix `_out_mix.mp4`.

### Command line options
- `--subtitle` – path to a folder or a single subtitle file.
- `--videoext` – extension of the video files (default: `.mp4`).
- `--srtext` – extension of subtitle files (default: `.srt`).
- `--coef` – volume mix coefficient for the original audio (default: `0.2`).
- `--output_folder` – directory where all intermediate and result files will be
  stored.

Run `python main.py -h` to see all available options.

## Notes
The `VOICE` subfolder should contain reference speaker audio files together with their texts and generated `speeds.csv` files. See `records/one_voice` for an example structure.
