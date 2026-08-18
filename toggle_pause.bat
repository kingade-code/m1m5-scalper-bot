@echo off
title M1-M5 Bot - Pause Toggle
cd /d "C:\Users\kinga\Documents\My Site\M1-M5 scalping"

if exist PAUSED (
    del PAUSED
    echo Bot RESUMED
    timeout /t 2
) else (
    echo. > PAUSED
    echo Bot PAUSED
    timeout /t 2
)
