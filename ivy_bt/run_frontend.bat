@echo off
title IvyBT Frontend
if not exist "..\pyquant\.venv" (
    echo Virtual environment not found at ..\pyquant\.venv
    pause
    exit /b
)
call ..\pyquant\.venv\Scripts\activate
streamlit run src/dashboard/Home.py
pause
