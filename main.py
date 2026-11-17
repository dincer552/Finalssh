import os
import sys
import json
import time
import queue
import socket
import threading
import shutil
import shlex
import subprocess
import urllib.request
import webbrowser
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from pathlib import Path

import paramiko

APP_NAME = "FinalSSH"
VERSION = "0.2.0"
REPO = "dincer552/Finalssh"
API_URL = f"https://api.github.com/repos/{REPO}/releases/latest"
BG = "#111318"
PANEL = "#191d25"
FIELD = "#222834"
TEXT = "#e7eaf0"
MUTED = "#9aa4b2"
ACCENT = "#4f8cff"
GREEN = "#38c98b"
RED = "#ff647c"


def app_dir():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent


def find_cloudflared():
    found = shutil.which("cloudflared")
    if found:
        return found
    candidates = [app_dir() / "cloudflared.exe", Path(sys.executable).parent / "cloudflared.exe"]
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    return None


class TrustOnFirstUse(paramiko.MissingHostKeyPolicy):
    def __init__(self, callback):
        self.callback = callback

    def missing_host_key(self, client, hostname, key):
        accepted = self.callback(hostname, key.get_name(), key.get_fingerprint().hex(":"))
        if not accepted:
            raise paramiko.SSHException("Sunucu anahtarı kullanıcı tarafından reddedildi.")
        client.get_host_keys().add(hostname, key.get_name(), key)
        known = Path.home() / ".finalssh" / "known_hosts"
        known.parent.mkdir(parents=True, exist_ok=True)
        client.save_host_keys(str(known))


class FinalSSH:
    def __init__(self, root):
        self.root = root
        self.root.title(f"{APP_NAME}  v{VERSION}")
        self.root.geometry("1000x680")
        self.root.minsize(760, 500)
        self.root.configure(bg=BG)
        self.events = queue.Queue()
        self.client = None
        self.channel = None
        self.connected = False
        self.closing = False
        self._build_ui()
        self.root.after(80, self._process_events)
        self.root.protocol("WM_DELETE_WINDOW", self.close)

    def _build_ui(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TFrame", background=BG)
        style.configure("TLabel", background=BG, foreground=TEXT, font=("Segoe UI", 10))
        style.configure("TButton", font=("Segoe UI", 10, "bold"), padding=(14, 8))
        style.configure("Connect.TButton", background=ACCENT, foreground="white")
        style.map("Connect.TButton", background=[("active", "#3979e8")])
        style.configure("TEntry", fieldbackground=FIELD, foreground=TEXT, insertcolor=TEXT, padding=8)
        style.configure("Status.TLabel", foreground=MUTED, font=("Segoe UI", 9))

        header = tk.Frame(self.root, bg=PANEL, height=58)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="FinalSSH", bg=PANEL, fg=TEXT,
                 font=("Segoe UI Semibold", 17)).pack(side="left", padx=20)
        self.version_label = tk.Label(header, text=f"v{VERSION}", bg=PANEL, fg=MUTED,
                                      font=("Segoe UI", 9))
        self.version_label.pack(side="left", pady=5)
        ttk.Button(header, text="Güncellemeleri kontrol et", command=self.check_updates).pack(side="right", padx=16)

        self.login = tk.Frame(self.root, bg=BG, padx=22, pady=18)
        self.login.pack(fill="x")
        fields = tk.Frame(self.login, bg=BG)
        fields.pack(fill="x")
        self.host = self._field(fields, "IP / Hostname", "192.168.1.100", 0)
        self.port = self._field(fields, "Port", "22", 1)
        self.username = self._field(fields, "Kullanıcı adı", "root", 2)
        key_block = tk.Frame(fields, bg=BG)
        key_block.grid(row=0, column=3, sticky="ew", padx=(0, 12))
        fields.grid_columnconfigure(3, weight=2)
        tk.Label(key_block, text="SSH Private Key (PEM / OpenSSH)", bg=BG, fg=MUTED,
                 font=("Segoe UI", 9)).pack(anchor="w", pady=(0, 5))
        key_row = tk.Frame(key_block, bg=BG)
        key_row.pack(fill="x")
        self.key_path = ttk.Entry(key_row)
        self.key_path.pack(side="left", fill="x", expand=True)
        ttk.Button(key_row, text="Dosya seç", command=self._browse_key).pack(side="left", padx=(6, 0))
        self.key_path.bind("<Return>", lambda _e: self.connect())

        mode_row = tk.Frame(self.login, bg=BG)
        mode_row.pack(fill="x", pady=(12, 0))
        tk.Label(mode_row, text="Bağlantı türü", bg=BG, fg=MUTED,
                 font=("Segoe UI", 9)).pack(side="left", padx=(0, 10))
        self.connection_mode = ttk.Combobox(mode_row, state="readonly",
                    values=["Normal SSH", "Cloudflare Tunnel"], width=22)
        self.connection_mode.current(0)
        self.connection_mode.pack(side="left")
        self.connection_mode.bind("<<ComboboxSelected>>", self._mode_changed)
        self.cf_frame = tk.Frame(self.login, bg=BG)
        self.cf_id = self._field(self.cf_frame, "Access Client ID (isteğe bağlı)", "", 0)
        self.cf_secret = self._field(self.cf_frame, "Access Client Secret (isteğe bağlı)", "", 1, show="•")
        tk.Label(self.cf_frame, text="cloudflared kurulu olmalı • Boş bırakılırsa tarayıcıyla Access girişi yapılır",
                 bg=BG, fg=MUTED, font=("Segoe UI", 8)).grid(row=1, column=0, columnspan=2, sticky="w", pady=(7,0))
        self.connect_btn = ttk.Button(self.login, text="Bağlan", style="Connect.TButton", command=self.connect)
        self.connect_btn.pack(anchor="e", pady=(12, 0))

        terminal_header = tk.Frame(self.root, bg=PANEL, height=42)
        terminal_header.pack(fill="x", padx=18)
        terminal_header.pack_propagate(False)
        tk.Label(terminal_header, text="TERMINAL", bg=PANEL, fg=MUTED,
                 font=("Segoe UI", 9, "bold")).pack(side="left", padx=12)
        self.status = tk.Label(terminal_header, text="● Bağlı değil", bg=PANEL, fg=MUTED,
                               font=("Segoe UI", 9))
        self.status.pack(side="left", padx=12)
        self.disconnect_btn = ttk.Button(terminal_header, text="Bağlantıyı kes",
                                         command=self.disconnect, state="disabled")
        self.disconnect_btn.pack(side="right", padx=8, pady=5)

        terminal_wrap = tk.Frame(self.root, bg=BG, padx=18, pady=0)
        terminal_wrap.pack(fill="both", expand=True)
        self.terminal = tk.Text(terminal_wrap, bg="#090b0f", fg="#d8e2ee",
                                insertbackground="white", selectbackground="#315b91",
                                font=("Consolas", 10), wrap="char", undo=False,
                                borderwidth=0, padx=12, pady=12, state="disabled")
        scroll = ttk.Scrollbar(terminal_wrap, command=self.terminal.yview)
        self.terminal.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.terminal.pack(side="left", fill="both", expand=True)
        self.terminal.bind("<KeyPress>", self._terminal_key)
        self.terminal.bind("<<Paste>>", self._paste)
        self.terminal.bind("<Button-1>", lambda _e: self.terminal.focus_set())

        footer = tk.Frame(self.root, bg=PANEL, height=30)
        footer.pack(fill="x", side="bottom")
        footer.pack_propagate(False)
        tk.Label(footer, text="SSH private key kullanılır • Anahtar dosyası diske kopyalanmaz",
                 bg=PANEL, fg=MUTED, font=("Segoe UI", 8)).pack(side="left", padx=12)
        self.footer_status = tk.Label(footer, text="Hazır", bg=PANEL, fg=MUTED,
                                      font=("Segoe UI", 8))
        self.footer_status.pack(side="right", padx=12)
        self._write("FinalSSH hazır. Bağlanmak için sunucu bilgilerini girin.\n")

    def _browse_key(self):
        path = filedialog.askopenfilename(
            title="SSH private key dosyasını seçin",
            filetypes=[("SSH key files", "*.pem *.key"), ("All files", "*.*")],
            parent=self.root
        )
        if path:
            self.key_path.delete(0, "end")
            self.key_path.insert(0, path)

    def _mode_changed(self, _event=None):
        if self.connection_mode.get() == "Cloudflare Tunnel":
            self.cf_frame.pack(fill="x", pady=(8, 0), before=self.connect_btn)
        else:
            self.cf_frame.pack_forget()

    def _field(self, parent, label, value, column, show=None):
        block = tk.Frame(parent, bg=BG)
        block.grid(row=0, column=column, sticky="ew", padx=(0, 12))
        parent.grid_columnconfigure(column, weight=1)
        tk.Label(block, text=label, bg=BG, fg=MUTED, font=("Segoe UI", 9)).pack(anchor="w", pady=(0, 5))
        entry = ttk.Entry(block, show=show)
        entry.insert(0, value)
        entry.pack(fill="x")
        return entry

    def _write(self, text):
        self.terminal.configure(state="normal")
        self.terminal.insert("end", text)
        self.terminal.see("end")
        self.terminal.configure(state="disabled")

    def _set_status(self, text, color=MUTED):
        self.status.configure(text=text, fg=color)

    def _ask_host_key(self, hostname, key_type, fingerprint):
        answer = threading.Event()
        result = {"accepted": False}
        def ask():
            result["accepted"] = messagebox.askyesno(
                "Yeni SSH sunucu anahtarı",
                f"Sunucu: {hostname}\nAnahtar türü: {key_type}\nParmak izi: {fingerprint}\n\n"
                "Bu sunucuya ilk kez bağlanıyorsunuz. Anahtara güveniyor musunuz?",
                parent=self.root)
            answer.set()
        self.root.after(0, ask)
        answer.wait()
        return result["accepted"]

    def connect(self):
        if self.connected:
            return
        host = self.host.get().strip()
        user = self.username.get().strip()
        key_path = self.key_path.get().strip()
        try:
            port = int(self.port.get().strip())
            if not host or not user or not key_path or not (1 <= port <= 65535):
                raise ValueError()
            if not Path(key_path).is_file():
                messagebox.showerror("SSH anahtarı bulunamadı", "Geçerli bir private key dosyası seçin.")
                return
        except ValueError:
            messagebox.showerror("Bilgi eksik", "IP/Host, port, kullanıcı adı ve PEM/OpenSSH private key dosyası seçin.")
            return
        mode = self.connection_mode.get()
        cf_id = self.cf_id.get().strip() if mode == "Cloudflare Tunnel" else ""
        cf_secret = self.cf_secret.get().strip() if mode == "Cloudflare Tunnel" else ""
        if mode == "Cloudflare Tunnel" and not find_cloudflared():
            messagebox.showerror("cloudflared bulunamadı",
                "Cloudflare Tunnel bağlantısı için cloudflared Windows istemcisini kurun ve PATH'e ekleyin.")
            return
        self.connect_btn.configure(state="disabled")
        self._set_status("● Bağlanıyor...", ACCENT)
        self._write(f"\n[{host}:{port}] {mode} bağlantısı kuruluyor...\n")
        threading.Thread(target=self._connect_worker,
                         args=(host, port, user, key_path, mode, cf_id, cf_secret), daemon=True).start()

    def _connect_worker(self, host, port, user, key_path, mode="Normal SSH", cf_id="", cf_secret=""):
        client = paramiko.SSHClient()
        known = Path.home() / ".finalssh" / "known_hosts"
        if known.exists():
            client.load_host_keys(str(known))
        client.set_missing_host_key_policy(TrustOnFirstUse(self._ask_host_key))
        proxy = None
        try:
            if mode == "Cloudflare Tunnel":
                cloudflared = find_cloudflared()
                if not cloudflared:
                    raise RuntimeError("cloudflared.exe bulunamadı. Kurup PATH'e ekleyin.")
                command_parts = [cloudflared, "access", "ssh", "--hostname", host]
                if bool(cf_id) != bool(cf_secret):
                    raise RuntimeError("Client ID ve Client Secret birlikte girilmelidir.")
                command = subprocess.list2cmdline(command_parts) if os.name == "nt" else shlex.join(command_parts)
                # cloudflared reads service tokens from its environment; do not expose
                # the secret in command-line arguments or persist it to disk.
                old_id = os.environ.get("TUNNEL_SERVICE_TOKEN_ID")
                old_secret = os.environ.get("TUNNEL_SERVICE_TOKEN_SECRET")
                try:
                    if cf_id and cf_secret:
                        os.environ["TUNNEL_SERVICE_TOKEN_ID"] = cf_id
                        os.environ["TUNNEL_SERVICE_TOKEN_SECRET"] = cf_secret
                    proxy = paramiko.ProxyCommand(command)
                finally:
                    if old_id is None:
                        os.environ.pop("TUNNEL_SERVICE_TOKEN_ID", None)
                    else:
                        os.environ["TUNNEL_SERVICE_TOKEN_ID"] = old_id
                    if old_secret is None:
                        os.environ.pop("TUNNEL_SERVICE_TOKEN_SECRET", None)
                    else:
                        os.environ["TUNNEL_SERVICE_TOKEN_SECRET"] = old_secret
                client.connect(hostname=host, port=port, username=user,
                               key_filename=key_path, sock=proxy, timeout=25,
                               banner_timeout=25, auth_timeout=20,
                               look_for_keys=True, allow_agent=True)
            else:
                client.connect(hostname=host, port=port, username=user,
                               key_filename=key_path, timeout=12, banner_timeout=12,
                               auth_timeout=15, look_for_keys=True, allow_agent=True)
            channel = client.invoke_shell(term="xterm-256color", width=120, height=32)
            channel.settimeout(0.0)
            self.events.put(("connected", client, channel, host, user))
        except Exception as exc:
            client.close()
            if proxy:
                proxy.close()
            self.events.put(("error", f"Bağlantı kurulamadı: {exc}"))

    def _process_events(self):
        try:
            while True:
                event = self.events.get_nowait()
                kind = event[0]
                if kind == "connected":
                    _, self.client, self.channel, host, user = event
                    self.connected = True
                    self.connect_btn.configure(state="disabled")
                    self.disconnect_btn.configure(state="normal")
                    self._set_status(f"● {user}@{host}", GREEN)
                    self.footer_status.configure(text="SSH bağlantısı aktif")
                    self._write(f"\n--- {user}@{host} bağlantısı kuruldu ---\n")
                    threading.Thread(target=self._read_worker, daemon=True).start()
                    self.terminal.focus_set()
                elif kind == "output":
                    self._write(event[1])
                elif kind == "closed":
                    self._finish_disconnect(event[1])
                elif kind == "error":
                    self._write(event[1] + "\n")
                    self._set_status("● Bağlantı hatası", RED)
                    self.footer_status.configure(text="Bağlantı başarısız")
                    self.connect_btn.configure(state="normal")
                elif kind == "update":
                    _, status, payload = event
                    if status == "current":
                        self.footer_status.configure(text="En güncel sürüm kullanılıyor")
                        messagebox.showinfo("Güncelleme", f"FinalSSH v{VERSION} güncel.")
                    elif status == "available":
                        self.footer_status.configure(text=f"Yeni sürüm: {payload.get('tag_name')}")
                        if messagebox.askyesno("Yeni sürüm bulundu",
                            f"Yeni sürüm {payload.get('tag_name')} bulundu.\nŞimdi güncellensin mi?"):
                            self._install_update(payload)
                    else:
                        self.footer_status.configure(text="Güncelleme kontrolü başarısız")
                        messagebox.showerror("Güncelleme", payload)
        except queue.Empty:
            pass
        if not self.closing:
            self.root.after(80, self._process_events)

    def _read_worker(self):
        try:
            while self.channel and not self.channel.closed:
                if self.channel.recv_ready():
                    data = self.channel.recv(32768)
                    if not data:
                        break
                    self.events.put(("output", data.decode("utf-8", errors="replace")))
                elif self.channel.exit_status_ready():
                    break
                else:
                    time.sleep(0.025)
        except Exception as exc:
            if self.connected:
                self.events.put(("output", f"\n[SSH okuma hatası: {exc}]\n"))
        self.events.put(("closed", "Uzak bağlantı kapandı."))

    def _terminal_key(self, event):
        if not self.connected or not self.channel:
            return "break"
        if event.state & 0x4 and event.keysym.lower() == "c":
            if event.state & 0x1:
                return None
            try:
                self.channel.send(b"\x03")
            except Exception:
                pass
            return "break"
        if event.state & 0x4 and event.keysym.lower() == "v":
            self._paste(None)
            return "break"
        mapping = {"Return": "\r", "BackSpace": "\x7f", "Tab": "\t",
                   "Up": "\x1b[A", "Down": "\x1b[B", "Right": "\x1b[C",
                   "Left": "\x1b[D", "Home": "\x1b[H", "End": "\x1b[F",
                   "Delete": "\x1b[3~"}
        payload = mapping.get(event.keysym)
        if payload is None and event.char:
            payload = event.char
        if payload:
            try:
                self.channel.send(payload.encode("utf-8"))
            except Exception as exc:
                self._write(f"\n[Gönderme hatası: {exc}]\n")
        return "break"

    def _paste(self, _event):
        if self.connected and self.channel:
            try:
                self.channel.send(self.root.clipboard_get().encode("utf-8"))
            except Exception:
                pass
        return "break"

    def disconnect(self):
        if self.client:
            try:
                self.client.close()
            except Exception:
                pass
        self._finish_disconnect("Bağlantı kapatıldı.")

    def _finish_disconnect(self, message):
        if self.connected or self.client:
            try:
                if self.client:
                    self.client.close()
            except Exception:
                pass
        self.client = None
        self.channel = None
        self.connected = False
        self.connect_btn.configure(state="normal")
        self.disconnect_btn.configure(state="disabled")
        self._set_status("● Bağlı değil", MUTED)
        self.footer_status.configure(text="Hazır")
        self._write(f"\n[{message}]\n")

    def check_updates(self):
        self.footer_status.configure(text="Güncellemeler kontrol ediliyor...")
        threading.Thread(target=self._check_updates_worker, daemon=True).start()

    def _check_updates_worker(self):
        try:
            request = urllib.request.Request(API_URL, headers={"User-Agent": APP_NAME})
            with urllib.request.urlopen(request, timeout=12) as response:
                release = json.loads(response.read().decode("utf-8"))
            latest = release.get("tag_name", "").lstrip("v")
            if not latest:
                raise RuntimeError("GitHub sürüm etiketi bulunamadı.")
            def version_key(value):
                parts = []
                for part in value.split("."):
                    digits = "".join(ch for ch in part if ch.isdigit())
                    parts.append(int(digits) if digits else 0)
                return tuple(parts)

            if version_key(latest) <= version_key(VERSION):
                self.events.put(("update", "current", release))
            else:
                self.events.put(("update", "available", release))
        except Exception as exc:
            self.events.put(("update", "error", str(exc)))

    def _install_update(self, release):
        assets = release.get("assets", [])
        asset = next((a for a in assets if a.get("name", "").lower().endswith(".exe")), None)
        if not asset:
            webbrowser.open(release.get("html_url", f"https://github.com/{REPO}/releases"))
            return
        if not getattr(sys, "frozen", False):
            messagebox.showinfo("Güncelleme", "Kaynak kod modundasınız. Yeni sürümü GitHub Releases sayfasından alın.")
            webbrowser.open(release.get("html_url", ""))
            return
        threading.Thread(target=self._download_update, args=(asset,), daemon=True).start()

    def _download_update(self, asset):
        try:
            req = urllib.request.Request(asset["browser_download_url"], headers={"User-Agent": APP_NAME})
            with urllib.request.urlopen(req, timeout=60) as response:
                data = response.read()
            current = Path(sys.executable).resolve()
            temp_exe = Path(os.environ.get("TEMP", str(current.parent))) / "FinalSSH-update.exe"
            temp_exe.write_bytes(data)
            bat = temp_exe.with_suffix(".bat")
            script = (
                "@echo off\r\n"
                "timeout /t 2 /nobreak >nul\r\n"
                f'copy /y "{temp_exe}" "{current}" >nul\r\n'
                f'start "" "{current}"\r\n'
                f'del "{temp_exe}"\r\n'
                'del "%~f0"\r\n'
            )
            bat.write_text(script, encoding="utf-8")
            os.startfile(str(bat))
            self.root.after(0, self.close)
        except Exception as exc:
            self.events.put(("output", f"\n[Güncelleme hatası: {exc}]\n"))

    def close(self):
        self.closing = True
        try:
            if self.client:
                self.client.close()
        except Exception:
            pass
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = FinalSSH(root)
    root.mainloop()
