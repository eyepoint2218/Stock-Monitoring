@echo off
python -m pip install -r requirements.txt
python -m pip install pyinstaller
pyinstaller --noconsole --onefile --name stock-monitor main.py
echo Build complete: dist\stock-monitor.exe
