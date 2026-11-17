# FinalSSH

Minimal Windows desktop SSH client built with Python, Tkinter and Paramiko.

## Features
- Connect using host/IP, port, username and a selected PEM/OpenSSH private key file (password authentication is not used).
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
Run `build.bat`. The script downloads the official Windows AMD64 `cloudflared` client and embeds it in the single-file executable. The executable is written to `dist\FinalSSH.exe`.

## Download and automatic updates

1. Download the first `FinalSSH.exe` from the repository's **Releases** page.
2. Run the EXE on Windows.
3. Every push to `main`/`master` (or manual run of the **Build and Publish FinalSSH** workflow) builds a new Windows EXE and publishes a versioned GitHub Release.
4. In the app, click **Güncellemeleri kontrol et**. If a newer release exists, accept the prompt; the app downloads the EXE, replaces itself after closing, and restarts.

GitHub Actions assigns each build a higher version automatically. The updater compares numeric version parts and ignores releases that are not newer. No manual tag creation is needed.

## Cloudflare Tunnel SSH

The app also supports SSH through a Cloudflare Tunnel protected by Cloudflare Access.

1. The packaged Windows EXE already contains the official `cloudflared.exe` client. No separate Cloudflare client installation is required.
2. In Cloudflare Zero Trust, create a Tunnel and publish the SSH hostname, routing it to the VM SSH service (commonly `localhost:22` on the tunnel host).
3. Configure a Cloudflare Access application and policy for that hostname.
4. In FinalSSH tick **Cloudflare Tunnel kullan**, enter the public Access hostname (for example `ssh.example.com`) in Host/IP, then enter the Linux SSH username and select your PEM/OpenSSH private key file.
5. Leave both Access token fields empty for browser-based Access login, or enter both a Service Token Client ID and Client Secret for a Service Auth policy.

FinalSSH bundles the Cloudflare client, but it does not create a Cloudflare account, Tunnel, DNS hostname, or Access policy for you. Those are configured once in your Cloudflare Zero Trust dashboard.

The Client ID and Client Secret are passed to the `cloudflared` child process through environment variables and are not saved by FinalSSH or exposed as command-line arguments. The SSH private key is used for VM authentication; the app does not ask for the VM account password. Cloudflare Tunnel's published route determines the origin SSH port (commonly 22); the port field is used for direct SSH connections.

## Security
- Credentials are not persisted.
- Host keys are confirmed on first connection and then checked on subsequent connections.
- Use only servers you are authorized to access.
