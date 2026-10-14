@echo off
REM Builds dist\ClassMark.exe (single file, no install needed)
cd /d %~dp0
if not exist .venv ( python -m venv .venv && .venv\Scripts\python -m pip install -r requirements.txt )
.venv\Scripts\pyinstaller --noconfirm --clean --onefile --windowed --name ClassMark ^
  --icon assets\icon.ico --add-data "assets;assets" ^
  --exclude-module tkinter --exclude-module matplotlib --exclude-module numpy ^
  --exclude-module pypdfium2 --exclude-module PIL.ImageQt main.py
echo.
echo Done: dist\ClassMark.exe
