cd /d C:\Users\d760dinyuk\Desktop\denemeler\Finalssh-main
python -m pyinstaller --noconfirm --clean --onefile --windowed --name FinalSSH --add-binary "vendor/cloudflared-windows-amd64.dll;." main.py