@echo off
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel% equ 0 (
  py -3 scripts\install-engine.py
) else (
  python scripts\install-engine.py
)
if errorlevel 1 (
  echo Installation failed. See the message above.
  pause
  exit /b 1
)
pause
