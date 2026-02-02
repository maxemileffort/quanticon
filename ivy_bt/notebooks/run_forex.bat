@echo off
setlocal

cd /d %~dp0
call ..\..\pyquant\.venv\Scripts\activate
python run_mtf_hmm_physics.py --universe forex --output-dir ..\outputs
pause