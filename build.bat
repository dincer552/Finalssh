@echo off
setlocal
py -3 -m pip install --upgrade pip
py -3 -m pip install -r requirements.txt
echo.
echo Downloading official Cloudflare Tunnel client...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='Stop'; $r=Invoke-RestMethod 'https://api.github.com/repos/cloudflare/cloudflared/releases/latest'; $a=$r.assets | Where-Object { $_.name -eq 'cloudflared-windows-amd64.exe' } | Select-Object -First 1; if (-not $a) { throw 'cloudflared Windows AMD64 asset not found' }; Invoke-WebRequest -Uri $a.browser_download_url -OutFile 'cloudflared.exe'; if ((Get-Item 'cloudflared.exe').Length -lt 1MB) { throw 'cloudflared download is invalid' }; Write-Host ('Downloaded '+$r.tag_name)"
if errorlevel 1 (
  echo Cloudflare client download failed. Build stopped.
  pause
  exit /b 1
)
py -3 -m PyInstaller --noconfirm --clean --onefile --windowed --name FinalSSH --add-binary "cloudflared.exe;." main.py
if errorlevel 1 (
  echo Build failed.
  pause
  exit /b 1
)
del cloudflared.exe
echo.
echo Build completed: dist\FinalSSH.exe
pause
