@echo off
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
title The Fire Bird - cinematic edit
cd /d "%~dp0"

ffmpeg -version >nul 2>nul
if errorlevel 1 (
  echo ffmpeg is not installed. Installing it now...
  winget install -e --id Gyan.FFmpeg --accept-source-agreements --accept-package-agreements
  echo.
  echo Done. Close this window and double-click montage.bat again.
  pause
  exit /b
)

set PY=
py -3 --version >nul 2>nul && set PY=py -3
if not defined PY python --version >nul 2>nul && set PY=python
if not defined PY (
  echo Python is not installed. Installing it now...
  winget install -e --id Python.Python.3.12 --accept-source-agreements --accept-package-agreements
  echo.
  echo Done. Close this window and double-click montage.bat again.
  pause
  exit /b
)

echo Making the film. This can take a while, keep this window open...
%PY% "%~dp0cinematic_edit.py" "%~dp0." %*
echo.
pause
