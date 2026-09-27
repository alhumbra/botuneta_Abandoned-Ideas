@echo off
setlocal
if "%~1"=="" (
  echo Drag an MSXPLAYer EXE onto this BAT file.
  pause
  exit /b 2
)
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 "%~dp0msxplayer_extract.py" "%~1" -o "%~dpn1_extracted" --roms
) else (
  python "%~dp0msxplayer_extract.py" "%~1" -o "%~dpn1_extracted" --roms
)
pause
