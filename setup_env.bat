@echo off
setlocal
cd /d "%~dp0"

if not exist .venv (
    python -m venv .venv || goto :err
)
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip || goto :err
python -m pip install -r requirements.txt || goto :err

echo.
echo Environment ready. Use run.bat to launch the app.
goto :eof

:err
echo.
echo Setup FAILED. Make sure Python 3.10+ is installed and on PATH.
exit /b 1
