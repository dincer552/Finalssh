# FinalSSH

Minimal Windows desktop SSH client built with Python, Tkinter and Paramiko.

## Features
- Connect using host/IP, port, username and password or available SSH agent/key.
- Interactive terminal in the application window.
- First-connection host-key confirmation; accepted keys are stored in `~/.finalssh/known_hosts`.
- Passwords are never saved.
- Check GitHub Releases and update the packaged Windows executable.

## Run from source
```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python main.py
```

## Build locally
Run `build.bat`. The executable is written to `dist\FinalSSH.exe`.

## GitHub release
Push a version tag such as `v0.1.1`. GitHub Actions builds the Windows executable and publishes it as a release asset. The in-app updater checks the latest release and can replace the running executable.

## Cloudflare Tunnel SSH

The app also supports SSH through a Cloudflare Tunnel protected by Cloudflare Access.

1. Install the Windows `cloudflared` client from [Cloudflare's official installation guide](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/), or place `cloudflared.exe` next to `FinalSSH.exe` (PATH is also supported).
2. In Cloudflare Zero Trust, publish the SSH hostname and route it to the VM SSH service (commonly `localhost:22` on the tunnel host).
3. Configure a Cloudflare Access application/policy for that hostname.
4. In FinalSSH choose **Cloudflare Tunnel**, enter the public Access hostname (for example `ssh.example.com`) in Host/IP, and enter the Linux SSH username/password or use an SSH key available to Paramiko.
5. Leave both Access token fields empty for browser-based Access login, or enter both a Service Token Client ID and Client Secret for a Service Auth policy.

The Client ID and Client Secret are passed to the `cloudflared` child process through environment variables and are not saved by FinalSSH or exposed as command-line arguments. The SSH username/password or key remains a separate authentication step on the VM. Cloudflare Tunnel's published route determines the origin SSH port (commonly 22); the port field is used for direct SSH connections.

## Security
- Credentials are not persisted.
- Host keys are confirmed on first connection and then checked on subsequent connections.
- Use only servers you are authorized to access.
