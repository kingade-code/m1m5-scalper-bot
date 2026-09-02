@echo off
title KingadeBot Updater
cd /d "%~dp0"

echo ============================================
echo    KingadeBot Update Tool
echo    Keeps your existing install up to date
echo    without a full reinstall.
echo ============================================
echo.

where python >nul 2>nul
if %errorlevel%==0 (
    python update_kingade.py %*
    goto :end
)

where py >nul 2>nul
if %errorlevel%==0 (
    py update_kingade.py %*
    goto :end
)

for %%d in (
    "%~dp0.venv\Scripts"
    "%~dp0venv\Scripts"
) do (
    if exist "%%~d\python.exe" (
        "%%~d\python.exe" update_kingade.py %*
        goto :end
    )
)

echo ERROR: Python not found. Install Python 3.10+ and re-run this file.
pause
exit /b 1

:end
echo.
pause