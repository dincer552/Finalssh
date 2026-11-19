@echo off
cd /d "%~dp0"
echo FinalSSH EXE oluşturuluyor...
"C:\Users\d760dinyuk\AppData\Local\Programs\Python\Python315\Scripts\pyinstaller.exe" --noconfirm --clean --onefile --windowed --name FinalSSH --add-binary "vendor/cloudflared-windows-amd64.dll;." --icon "FinalSSH.ico" --collect-all cryptography main.py
if %errorlevel% neq 0 (
    echo Hata oluştu!
    pause
    exit /b 1
)
copy /Y dist\FinalSSH.exe FinalSSH.exe
echo.
echo Basarili! FinalSSH.exe güncellendi.
echo Dosya boyutu: 
for %%I in (FinalSSH.exe) do echo %%~zI bytes
pause