@echo off
setlocal enabledelayedexpansion

REM === Set the path to the folder containing the .srt files ===
set "SUBTITLE_FOLDER=local"

CALL "venv\Scripts\activate.bat"

REM === Main loop ===
:loop
python -m srt2audiotrack --subtitle "%SUBTITLE_FOLDER%" --output_folder "%SUBTITLE_FOLDER%"
IF ERRORLEVEL 1 (
    echo [ERROR] Script crashed. Waiting before retry...
    timeout /t 5
)
goto loop