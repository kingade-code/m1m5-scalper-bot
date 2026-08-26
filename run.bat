@echo off
title M1-M5 Scalper Bot
cd /d "C:\Users\kinga\Documents\My Site\M1-M5 scalping"
taskkill /F /IM pythonw.exe >nul 2>&1
python main.py
pause
