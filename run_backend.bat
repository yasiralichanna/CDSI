@echo off
title CDSI Backend Server
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
echo Starting CDSI Backend on http://localhost:8000 ...
.venv\Scripts\python.exe -m uvicorn dashboard.backend.main:app --host 0.0.0.0 --port 8000
pause
