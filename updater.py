"""GitHub Release updater for FinalSSH.

Downloads the latest release EXE in small, retryable parts, then replaces
and restarts the running one-file Windows application.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from tkinter import messagebox

from build_info import BUILD_VERSION

REPO = "dincer552/Finalssh"
API_URL = f"https://api.github.com/repos/{REPO}/releases/latest"
RELEASE_URL = f"https://github.com/{REPO}/releases/latest"
USER_AGENT = "FinalSSH-Updater"
PART_RE = re.compile(r"^FinalSSH_latest\.part(\d+)$")


def _version_tuple(value: str) -> tuple[int, ...]:
    match = re.search(r"(\d+(?:\.\d+)+)", str(value or ""))
    if not match:
        return ()
    return tuple(int(part) for part in match.group(1).split("."))


def _release_version(payload: dict) -> str:
    name = str(payload.get("name") or "").strip()
    match = re.search(r"v?(\d+(?:\.\d+)+)", name, re.IGNORECASE)
    if match:
        return f"v{match.group(1)}"

    tag = str(payload.get("tag_name") or "").strip()
    if _version_tuple(tag):
        return tag if tag.lower().startswith("v") else f"v{tag}"
    raise RuntimeError("GitHub Release sürümü okunamadı.")


def _request_json() -> dict:
    request = urllib.request.Request(
        API_URL,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/vnd.github+json",
            "Cache-Control": "no-cache",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def check_for_update() -> dict:
    """Compare the installed build with the latest published release."""
    payload = _request_json()
    latest_version = _release_version(payload)
    latest_tuple = _version_tuple(latest_version)
    current_tuple = _version_tuple(str(BUILD_VERSION or ""))
    if not latest_tuple:
        raise RuntimeError("GitHub Release sürüm numarası geçersiz.")

    return {
        "available": bool(current_tuple and latest_tuple > current_tuple),
        "version": latest_version,
        "tag_name": payload.get("tag_name", ""),
        "html_url": payload.get("html_url", RELEASE_URL),
    }


def _release_parts() -> list[dict]:
    payload = _request_json()
    parts = []
    for asset in payload.get("assets", []):
        name = str(asset.get("name") or "")
        match = PART_RE.match(name)
        if not match:
            continue
        parts.append({
            "name": name,
            "number": int(match.group(1)),
            "size": int(asset.get("size", 0)),
            "url": str(asset.get("browser_download_url") or ""),
        })
    parts.sort(key=lambda item: item["number"])
    if not parts:
        raise RuntimeError("Son GitHub Release içinde güncelleme parçaları bulunamadı.")
    if [part["number"] for part in parts] != list(range(len(parts))):
        raise RuntimeError("Güncelleme parçaları eksik veya sırasız.")
    if any(not part["url"] or part["size"] <= 0 for part in parts):
        raise RuntimeError("Güncelleme parçası bilgileri geçersiz.")
    return parts


def _download_part(part: dict, folder: Path, progress=None,
                   done_before: int = 0, total: int = 0,
                   started: float | None = None) -> Path:
    target = folder / part["name"]
    expected = part["size"]

    for attempt in range(1, 9):
        downloaded = 0
        try:
            request = urllib.request.Request(
                part["url"],
                headers={
                    "User-Agent": USER_AGENT,
                    "Accept": "application/octet-stream",
                    "Cache-Control": "no-cache",
                    "Pragma": "no-cache",
                    "Accept-Encoding": "identity",
                },
            )
            with urllib.request.urlopen(request, timeout=120) as response:
                with target.open("wb") as output:
                    while True:
                        data = response.read(256 * 1024)
                        if not data:
                            break
                        output.write(data)
                        downloaded += len(data)
                        if progress:
                            elapsed = max(time.monotonic() - (started or time.monotonic()), 0.001)
                            progress(done_before + downloaded, total,
                                     (done_before + downloaded) / elapsed)

            if downloaded != expected:
                target.unlink(missing_ok=True)
                if attempt == 8:
                    raise RuntimeError(
                        f"{part['name']} eksik indirildi ({downloaded:,}/{expected:,} byte)."
                    )
                time.sleep(min(attempt, 5))
                continue
            return target
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as exc:
            target.unlink(missing_ok=True)
            if attempt == 8:
                raise RuntimeError(f"{part['name']} indirilemedi: {exc}") from exc
            time.sleep(min(attempt, 5))
    raise RuntimeError(f"{part['name']} indirilemedi.")


def _download_latest(progress=None) -> Path:
    """Download 2 MiB release parts and join them into a complete EXE."""
    temp_dir = Path(tempfile.mkdtemp(prefix="finalssh_update_"))
    target = temp_dir / "FinalSSH_update.exe"
    try:
        parts = _release_parts()
        total = sum(part["size"] for part in parts)
        done = 0
        started = time.monotonic()
        part_files = []

        for part in parts:
            path = _download_part(
                part, temp_dir, progress=progress,
                done_before=done, total=total, started=started,
            )
            part_files.append(path)
            done += part["size"]

        with target.open("wb") as output:
            for part_file in part_files:
                with part_file.open("rb") as source:
                    while True:
                        data = source.read(1024 * 1024)
                        if not data:
                            break
                        output.write(data)

        if not target.is_file() or target.stat().st_size != total:
            raise RuntimeError("Güncelleme dosyası birleştirilemedi veya boyutu doğrulanamadı.")
        return target
    except Exception:
        for item in temp_dir.glob("*"):
            item.unlink(missing_ok=True)
        try:
            temp_dir.rmdir()
        except OSError:
            pass
        raise


def _start_replacement(downloaded: Path, current_exe: Path) -> None:
    script = Path(tempfile.gettempdir()) / (
        f"finalssh_update_{os.getpid()}_{time.time_ns()}.ps1"
    )
    script.write_text(
        r"""
param([string]$Source, [string]$Target, [int]$ParentPid, [string]$ScriptPath)
$ErrorActionPreference = "Stop"
$TempFolder = Split-Path -Parent $Source
try {
    for ($i = 0; $i -lt 120; $i++) {
        if (-not (Get-Process -Id $ParentPid -ErrorAction SilentlyContinue)) { break }
        Start-Sleep -Milliseconds 250
    }
    if (Get-Process -Id $ParentPid -ErrorAction SilentlyContinue) {
        throw "FinalSSH işlemi kapatılamadı."
    }

    $installed = $false
    for ($i = 0; $i -lt 60; $i++) {
        try {
            $staging = "$Target.new"
            Copy-Item -LiteralPath $Source -Destination $staging -Force
            if (Test-Path -LiteralPath $Target) {
                Remove-Item -LiteralPath $Target -Force -ErrorAction Stop
            }
            Move-Item -LiteralPath $staging -Destination $Target -Force -ErrorAction Stop
            $installed = $true
            break
        } catch {
            if ($i -eq 59) { throw }
            Start-Sleep -Seconds 1
        }
    }

    if (-not $installed -or -not (Test-Path -LiteralPath $Target)) {
        throw "Yeni FinalSSH dosyası hedefe taşınamadı."
    }

    Start-Process -FilePath $Target
} catch {
    Add-Type -AssemblyName PresentationFramework
    [System.Windows.MessageBox]::Show(
        ("Güncelleme kurulamadı." + [Environment]::NewLine + [Environment]::NewLine + $_.Exception.Message),
        "FinalSSH - Güncelleme",
        [System.Windows.MessageBoxButton]::OK,
        [System.Windows.MessageBoxImage]::Error
    ) | Out-Null
} finally {
    Remove-Item -LiteralPath $ScriptPath -Force -ErrorAction SilentlyContinue
    Start-Sleep -Milliseconds 500
    Remove-Item -LiteralPath $TempFolder -Recurse -Force -ErrorAction SilentlyContinue
}
""".strip(),
        encoding="utf-8-sig",
    )

    subprocess.Popen(
        [
            "powershell.exe", "-NoProfile", "-NonInteractive",
            "-ExecutionPolicy", "Bypass", "-WindowStyle", "Hidden",
            "-File", str(script),
            "-Source", str(downloaded),
            "-Target", str(current_exe),
            "-ParentPid", str(os.getpid()),
            "-ScriptPath", str(script),
        ],
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        close_fds=True,
    )


def start_update(parent, button=None) -> None:
    """Download and install the newest release without blocking the UI."""
    if getattr(parent, "_update_running", False):
        return
    parent._update_running = True
    if button is None:
        button = getattr(parent, "_update_button", None)

    def set_button(text: str, enabled: bool = False) -> None:
        if button is not None:
            try:
                button.configure(text=text, state="normal" if enabled else "disabled")
            except Exception:
                pass

    def finish(error: str | None = None) -> None:
        parent._update_running = False
        set_button("Güncelle", True)
        if error:
            try:
                messagebox.showerror("FinalSSH - Güncelleme", error, parent=parent)
            except Exception:
                pass

    def worker() -> None:
        try:
            if not getattr(sys, "frozen", False):
                raise RuntimeError("Kaynak kod modunda otomatik EXE güncellemesi yapılamaz.")
            current = Path(sys.executable).resolve()
            parent.after(0, lambda: set_button("Hazırlanıyor..."))

            def report(done: int, total: int, speed: float) -> None:
                percent = int(done * 100 / total) if total else 0
                mb = done / (1024 * 1024)
                total_mb = total / (1024 * 1024) if total else 0
                speed_mb = speed / (1024 * 1024)
                parent.after(0, lambda: set_button(f"İndir %{percent}"))
                parent.after(
                    0,
                    lambda: parent.title(
                        f"FinalSSH — Güncelleme %{percent} "
                        f"({mb:.1f}/{total_mb:.1f} MB, {speed_mb:.1f} MB/sn)"
                    ),
                )

            downloaded = _download_latest(progress=report)
            parent.after(0, lambda: parent.title("FinalSSH — Güncelleme kuruluyor..."))
            _start_replacement(downloaded, current)
            parent.after(0, parent.destroy)
        except Exception as exc:
            parent.after(0, lambda message=str(exc): finish(message))

    set_button("Kontrol ediliyor...")
    threading.Thread(target=worker, name="finalssh-updater", daemon=True).start()
