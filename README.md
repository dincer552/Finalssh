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

## Security
- Credentials are not persisted.
- Host keys are confirmed on first connection and then checked on subsequent connections.
- Use only servers you are authorized to access.
