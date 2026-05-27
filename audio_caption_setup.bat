@echo off
setlocal enabledelayedexpansion
title Audio Caption Generator — Setup

echo.
echo ============================================================
echo   Audio Caption Generator — Windows Setup (Python 3.12)
echo ============================================================
echo.

:: ── Check Python 3.12 ─────────────────────────────────────────────────────
py -3.12 --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python 3.12 is not installed.
    echo         Install it with:  winget install Python.Python.3.12
    echo         Then re-run this script.
    pause
    exit /b 1
)
for /f "tokens=*" %%v in ('py -3.12 --version') do echo [OK] Found %%v

:: ── Check ffmpeg ──────────────────────────────────────────────────────────
ffmpeg -version >nul 2>&1
if errorlevel 1 (
    echo.
    echo [WARNING] ffmpeg is NOT installed or not in PATH.
    echo           Speed adjustment will NOT work without ffmpeg.
    echo.
    echo  Install with:  winget install ffmpeg
    echo.
    echo  Press any key to continue setup anyway, or Ctrl+C to abort.
    pause >nul
) else (
    echo [OK] ffmpeg found.
)

:: ── Create virtual environment ─────────────────────────────────────────────
if not exist ".venv" (
    echo.
    echo [SETUP] Creating Python 3.12 virtual environment...
    py -3.12 -m venv .venv
    echo [OK] Virtual environment created.
) else (
    echo [OK] Virtual environment already exists.
)

:: ── Upgrade pip ───────────────────────────────────────────────────────────
echo.
echo [SETUP] Upgrading pip...
.venv\Scripts\python.exe -m pip install --upgrade pip -q

:: ── Install dependencies ──────────────────────────────────────────────────
echo.
echo [SETUP] Installing Python dependencies (this may take a few minutes)...
.venv\Scripts\python.exe -m pip install -r requirements.txt

if errorlevel 1 (
    echo.
    echo [ERROR] Dependency installation failed. Check the output above.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo   Setup complete!
echo ============================================================
echo.
echo   To run the app:
echo     1. Activate the virtual environment:
echo           .venv\Scripts\activate
echo     2. Start the app:
echo           python app.py
echo     3. Open your browser at:
echo           http://127.0.0.1:7860
echo.
echo   Or just double-click:  run.bat
echo.

:: ── Create run.bat ────────────────────────────────────────────────────────
if not exist "run.bat" (
    (
        echo @echo off
        echo call .venv\Scripts\activate.bat
        echo python app.py
    ) > run.bat
    echo [OK] Created run.bat for easy startup.
)

echo Press any key to launch the app now...
pause >nul
.venv\Scripts\python.exe app.py

