@echo off
setlocal
cd /d "%~dp0"
if not exist .venv (
    echo .venv not found. Run setup_env.bat first.
    exit /b 1
)
call .venv\Scripts\activate.bat
python -m forza_radio_maker
