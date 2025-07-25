@echo off
REM Batch script to activate conda environment, find .srt files, and run the script with N threads

REM Set the path to the folder containing the .srt files
set "SUBTITLE_FOLDER=one_voice\input"
set "OUTPUT_FOLDER=one_voice\output"

REM Activate Anaconda environment
CALL C:\ProgramData\anaconda3\Scripts\activate.bat C:\ProgramData\anaconda3
CALL conda activate f5-tts-demucs

REM Find all .srt files (non-recursively) and run main.py with threading
setlocal enabledelayedexpansion
REM :loop

python ..\main.py --subtitle %SUBTITLE_FOLDER% --output_folder %OUTPUT_FOLDER%

REM goto loop
REM Deactivate conda environment
CALL conda deactivate

echo Done!