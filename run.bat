@echo off
title Carbon-Cost Estimator
cd /d "%~dp0"
if not exist ".venv\Scripts\streamlit.exe" (
    echo Creating virtual environment and installing dependencies - first run only...
    python -m venv .venv
    .venv\Scripts\python.exe -m pip install --upgrade pip
    .venv\Scripts\python.exe -m pip install -r requirements.txt
)
echo Starting dashboard at http://localhost:8501 ...
".venv\Scripts\streamlit.exe" run app.py
pause
