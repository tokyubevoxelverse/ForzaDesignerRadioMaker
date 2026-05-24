@echo off
setlocal
cd /d "%~dp0"

if not exist .venv (
    python -m venv .venv || goto :err
)
call .venv\Scripts\activate.bat

python -m pip install --upgrade pip || goto :err
python -m pip install -r requirements.txt pyinstaller || goto :err

rmdir /s /q build_pyi 2>nul
rmdir /s /q dist 2>nul
del /q ForzaHorizonRadioMaker.spec 2>nul

REM yt-dlp is NOT bundled — the EXE downloads the latest yt-dlp.exe to
REM %LOCALAPPDATA%\ForzaHorizonRadioMaker\bin on first Spotify/YouTube build.
pyinstaller ^
    --noconfirm ^
    --clean ^
    --onefile ^
    --name ForzaHorizonRadioMaker ^
    --windowed ^
    --collect-all imageio_ffmpeg ^
    --collect-submodules PySide6 ^
    --collect-submodules forza_radio_maker ^
    --add-data "forza_radio_maker\resources;forza_radio_maker\resources" ^
    --paths . ^
    --workpath build_pyi ^
    launcher.py

if errorlevel 1 goto :err

echo.
echo Built: dist\ForzaHorizonRadioMaker.exe
goto :eof

:err
echo.
echo BUILD FAILED.
exit /b 1
