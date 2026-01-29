@echo off
title IvyBT Backend
if not exist "..\pyquant\.venv" (
    echo Virtual environment not found at ..\pyquant\.venv
    pause
    exit /b
)
call ..\pyquant\.venv\Scripts\activate
python src/api/main.py
pause
