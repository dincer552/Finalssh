# Third-party notices

## QudsLab / Cloudflared DLL

FinalSSH packages the Windows AMD64 shared library from
[QudsLab / Cloudflared](https://github.com/QudsLab/Cloudflared), pinned to
commit `ef1b0c079a3110234a17f7764eb83d5c9162350f` (project release
`2026.7.1`).

DLL file: `cloudflared-windows-amd64.dll`  
SHA-256: `d4f87009251fc952606dba6d8ad54f4a003ec290f93f37593c38badd1a60e745`

FinalSSH uses the library's C exports through Python `ctypes`:
`CloudflaredInit`, `CloudflaredRun`, and `CloudflaredStop`. The DLL is
loaded from the private PyInstaller one-file runtime directory. The user does
not receive or launch a separate Cloudflare executable or DLL.

QudsLab / Cloudflared is licensed under Apache License 2.0. A copy is included
at [THIRD_PARTY_LICENSES/Apache-2.0.txt](THIRD_PARTY_LICENSES/Apache-2.0.txt).

## Cloudflare cloudflared

QudsLab's DLL is based on the
[official Cloudflare cloudflared project](https://github.com/cloudflare/cloudflared),
which provides the Cloudflare Tunnel and Access transport used by FinalSSH.
Cloudflare's project is distributed under Apache License 2.0 with its
additional Runtime Library Exception. See the
[official Cloudflare license notice](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/downloads/license/).

