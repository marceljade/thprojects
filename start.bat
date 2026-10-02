@echo off
setlocal
title Projektmanagement T^&H
cd /d "%~dp0backend"

rem ---- Python finden (Launcher oder python.exe)
set PY=
py -3 -c "import sys" >nul 2>&1 && set PY=py -3
if "%PY%"=="" ( python -c "import sys" >nul 2>&1 && set PY=python )
if "%PY%"=="" (
  echo Python 3.11 oder neuer wurde nicht gefunden. Bitte von https://www.python.org/downloads/ installieren
  echo und dabei "Add python.exe to PATH" anhaken.
  pause
  exit /b 1
)

rem ---- Beim ersten Start: virtuelle Umgebung anlegen und Pakete installieren
if not exist ".venv\Scripts\python.exe" (
  echo Erster Start: Umgebung wird eingerichtet, das dauert etwa eine Minute ...
  %PY% -m venv .venv || (echo Konnte die virtuelle Umgebung nicht anlegen. & pause & exit /b 1)
  ".venv\Scripts\python.exe" -m pip install --quiet --upgrade pip
  ".venv\Scripts\python.exe" -m pip install --quiet -r requirements.txt || (echo Paketinstallation fehlgeschlagen. & pause & exit /b 1)
)

rem ---- Nach einem Update: fehlende Pakete nachinstallieren (z. B. pywin32 fuer die Outlook-Anbindung)
".venv\Scripts\python.exe" -c "import win32com" >nul 2>&1 || ".venv\Scripts\python.exe" -m pip install --quiet -r requirements.txt

rem ---- Server starten (eigenes, minimiertes Fenster) und Browser oeffnen
start "Projektmanagement T&H - Server (Fenster schliessen beendet die Anwendung)" /min ".venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8765
timeout /t 3 /nobreak >nul
start "" "http://localhost:8765"
endlocal
