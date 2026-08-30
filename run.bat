@echo off
title M1-M5 Scalper Bot
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
    taskkill /F /IM pythonw.exe >nul 2>&1
    start "" /D "%~dp0" ".venv\Scripts\python.exe" main.py
) else if exist "%LocalAppData%\Programs\Python\Python314\python.exe" (
    taskkill /F /IM pythonw.exe >nul 2>&1
    start "" /D "%~dp0" "%LocalAppData%\Programs\Python\Python314\python.exe" main.py
) else (
    taskkill /F /IM pythonw.exe >nul 2>&1
    start "" /D "%~dp0" python main.py
)
timeout /t 2