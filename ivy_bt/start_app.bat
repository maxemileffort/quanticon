@echo off
echo Starting IvyBT...
if not exist "..\pyquant\.venv" (
    echo Virtual environment not found at ..\pyquant\.venv
    pause
    exit /b
)

start "IvyBT Backend" run_backend.bat
start "IvyBT Frontend" run_frontend.bat

echo App processes started.
