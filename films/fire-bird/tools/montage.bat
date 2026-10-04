@echo off
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
title The Fire Bird - cinematic edit

where ffmpeg >nul 2>nul
if errorlevel 1 (
  echo ffmpeg is not installed. Installing it now...
  winget install -e --id Gyan.FFmpeg
  echo.
  echo Close this window and double-click montage.bat again.
  pause
  exit /b
)

where python >nul 2>nul
if errorlevel 1 (
  echo Python is not installed. Installing it now...
  winget install -e --id Python.Python.3.12
  echo.
  echo Close this window and double-click montage.bat again.
  pause
  exit /b
)

python "%~dp0cinematic_edit.py" "%~dp0." %*
echo.
pause
