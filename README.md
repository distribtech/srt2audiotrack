# srt2audiotrack

Make from directory with videos and srt files videos with english audiotrack.

For installation:

In Windows:

1. Create conda environment:
conda create -n f5-tts-demucs python=3.10
conda activate f5-tts-demucs

2. Install f5-tts (https://github.com/SWivid/F5-TTS/tree/main)
pip install f5-tts

then install demucs (https://github.com/adefossez/demucs)
python -m pip install -U demucs

3. Run the web interface:
python web_app.py

Open your browser at http://localhost:5000. Use the **Advanced** tab to adjust
all parameters that were available in the console version. Output videos will be
created in the selected folder with the specified suffix.

Result must be:
https://fex.net/ru/s/fctovr0

## Running tests

Install the dependencies listed in `requirements.txt` and run the test suite
with [pytest](https://pytest.org/):

```bash
pytest
```

ToDo:

1. Make something with short not-generated segments.
2. Test work with single file.
3. Refactor everything.
