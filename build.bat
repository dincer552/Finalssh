@echo off
setlocal
py -3 -m pip install --upgrade pip
py -3 -m pip install -r requirements.txt
py -3 -m PyInstaller --noconfirm --clean --onefile --windowed --name FinalSSH main.py
echo.
echo Build completed: dist\FinalSSH.exe
pause
