@echo off
echo Activating virtual environment
call .venv/Scripts/activate
echo Running stock_screener.py
python stock_screener.py
echo Running generate_charts.py
python generate_charts.py
echo Running agent_analysis.py
python agent_analysis.py
echo Deactivating virtual environment
deactivate
echo Done
pause
