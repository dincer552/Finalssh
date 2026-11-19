import os
import sys
import ctypes
import json
import time
import queue
import socket
import threading
import urllib.request
import webbrowser
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from pathlib import Path

import paramiko

from build_info import BUILD_VERSION as VERSION
from updater import check_for_update, start_update

APP_NAME = "FinalSSH"
REPO = "dincer552/Finalssh"
BG = "#ffffff"
PANEL = "#f4f4f5"
FIELD = "#ffffff"
TEXT = "#18181b"
MUTED = "#71717a"
ACCENT = "#2563eb"
GREEN = "#16a34a"
RED = "#dc2626"


def app_dir():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent


CLOUDFLARED_DLL_NAME = "cloudflared-windows-amd64.dll"


def find_cloudflared_dll():
    if getattr(sys, "frozen", False):
        bundled_dir = getattr(sys, "_MEIPASS", None)
        if not bundled_dir:
            return None
        candidate = Path(bundled_dir) / CLOUDFLARED_DLL_NAME
        return candidate if candidate.is_file() else None

    base = Path(__file__).resolve().parent
    for candidate in (base / "vendor" / CLOUDFLARED_DLL_NAME, base / CLOUDFLARED_DLL_NAME):
        if candidate.is_file():
            return candidate
    return None


def load_cloudflared_dll():
    dll_path = find_cloudflared_dll()
    if not dll_path:
        raise RuntimeError(
            "QudsLab Cloudflared DLL bulunamadı. FinalSSH paketini GitHub Actions Release üzerinden indirin."
        )

    directory_handle = None
    try:
        if os.name == "nt" and hasattr(os, "add_dll_directory"):
            directory_handle = os.add_dll_directory(str(dll_path.parent))
        library = ctypes.CDLL(str(dll_path))
        library.CloudflaredInit.argtypes = []
        library.CloudflaredInit.restype = ctypes.c_int
        library.CloudflaredRun.argtypes = [ctypes.c_char_p]
        library.CloudflaredRun.restype = ctypes.c_int
        library.CloudflaredStop.argtypes = []
        library.CloudflaredStop.restype = ctypes.c_int
        library.CloudflaredVersion.argtypes = []
        library.CloudflaredVersion.restype = ctypes.c_char_p
        library._finalssh_dll_directory = directory_handle
        return library
    except Exception:
        if directory_handle:
            directory_handle.close()
        raise


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
        try:
            self.root.iconbitmap(default=str(app_dir() / "FinalSSH.ico"))
        except Exception:
            pass
        self.events = queue.Queue()
        self.client = None
        self.channel = None
        self.cf_runtime = None
        self.connected = False
        self.closing = False
        self._update_check_running = False
        self._update_available = False
        self._update_button = None
        self._manual_update_button = None
        self._update_build_label = None
        self._update_running = False
        self._build_ui()
        self._load_settings()
        self.root.after(80, self._process_events)
        self.root.after(2000, self._schedule_update_check)
        self.root.protocol("WM_DELETE_WINDOW", self.close)

    def _build_ui(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TFrame", background=BG)
        style.configure("TLabel", background=BG, foreground=TEXT, font=("Segoe UI", 10))
        style.configure("TButton", font=("Segoe UI", 10, "bold"), padding=(14, 8))
        style.configure("Connect.TButton", background=ACCENT, foreground="white")
        style.map("Connect.TButton", background=[("active", "#1d4ed8")])
        style.configure("TEntry", fieldbackground=FIELD, foreground=TEXT, insertcolor=TEXT, padding=8, borderwidth=1, relief="solid")
        style.configure("Status.TLabel", foreground=MUTED, font=("Segoe UI", 9))
        style.configure("UpdateBuild.TLabel", background=PANEL, foreground=GREEN,
                        font=("Segoe UI", 7, "bold"))
        style.configure("CompactUpdate.TButton", background=ACCENT, foreground="white",
                        font=("Segoe UI", 8, "bold"), borderwidth=0, padding=(7, 2))
        style.map("CompactUpdate.TButton",
                  background=[("active", "#1d4ed8"), ("disabled", "#d1d5db")])
        style.configure("CheckUpdate.TButton", font=("Segoe UI", 8), padding=(7, 3))

        header = tk.Frame(self.root, bg=PANEL, height=58)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="FinalSSH", bg=PANEL, fg=TEXT,
                 font=("Segoe UI Semibold", 17)).pack(side="left", padx=20)
        self.version_label = tk.Label(header, text=f"v{VERSION}", bg=PANEL, fg=MUTED,
                                      font=("Segoe UI", 9))
        self.version_label.pack(side="left", pady=5)
        update_controls = tk.Frame(header, bg=PANEL)
        update_controls.pack(side="right", padx=12, pady=5)

        self._manual_update_button = ttk.Button(
            update_controls, text="↻ Denetle", style="CheckUpdate.TButton",
            command=self._manual_update_check, width=9
        )
        self._manual_update_button.pack(side="left", padx=(0, 6), anchor="n")

        update_stack = tk.Frame(update_controls, bg=PANEL)
        update_stack.pack(side="left", anchor="n")
        self._update_button = ttk.Button(
            update_stack, text="Güncelle", style="CompactUpdate.TButton",
            command=self._start_update, width=10, state="disabled"
        )
        self._update_button.pack(side="top", fill="x")
        self._update_build_label = ttk.Label(
            update_stack, text="", style="UpdateBuild.TLabel",
            anchor="center", state="disabled"
        )
        self._update_build_label.pack(side="top", fill="x", pady=(1, 0))

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
        self.cloudflare_enabled = tk.BooleanVar(value=False)
        ttk.Checkbutton(mode_row, text="Cloudflare Tunnel kullan",
                        variable=self.cloudflare_enabled,
                        command=self._mode_changed).pack(side="left")
        self.cf_frame = tk.Frame(self.login, bg=BG)
        self.cf_id = self._field(self.cf_frame, "Access Client ID (isteğe bağlı)", "", 0)
        self.cf_secret = self._field(self.cf_frame, "Access Client Secret (isteğe bağlı)", "", 1, show="•")
        
        # Advanced Cloudflare options
        adv_row = tk.Frame(self.cf_frame, bg=BG)
        adv_row.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        self.cf_http2 = tk.BooleanVar(value=True)  # Default True for corporate networks
        ttk.Checkbutton(adv_row, text="HTTP/2 zorla (QUIC engelse)", variable=self.cf_http2).pack(side="left")
        self.cf_no_tls_verify = tk.BooleanVar(value=False)
        ttk.Checkbutton(adv_row, text="TLS doğrulamayı atla (SSL inspection varsa)", variable=self.cf_no_tls_verify).pack(side="left", padx=(12, 0))
        
        # Proxy settings
        proxy_row = tk.Frame(self.cf_frame, bg=BG)
        proxy_row.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        self.cf_proxy_http = self._field(proxy_row, "HTTP Proxy (isteğe bağlı)", "", 0)
        self.cf_proxy_https = self._field(proxy_row, "HTTPS Proxy (isteğe bağlı)", "", 1)
        
        tk.Label(self.cf_frame, text="Cloudflare bağlantı motoru uygulamaya gömülüdür • Boş bırakılırsa tarayıcıyla Access girişi yapılır",
                 bg=BG, fg=MUTED, font=("Segoe UI", 8)).grid(row=4, column=0, columnspan=2, sticky="w", pady=(7,0))
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
        self.copy_terminal_btn = ttk.Button(terminal_header, text="📋 Kopyala",
                                            command=self._copy_terminal, width=14)
        self.copy_terminal_btn.pack(side="right", padx=6, pady=6)
        self.paste_terminal_btn = ttk.Button(terminal_header, text="📥 Yapıştır",
                                             command=self._paste_to_terminal, width=14)
        self.paste_terminal_btn.pack(side="right", padx=6, pady=6)
        self.disconnect_btn = ttk.Button(terminal_header, text="Bağlantıyı Kes",
                                         command=self.disconnect, state="disabled", width=14)
        self.disconnect_btn.pack(side="right", padx=8, pady=6)

        terminal_wrap = tk.Frame(self.root, bg=BG, padx=18, pady=0)
        terminal_wrap.pack(fill="both", expand=True)
        self.terminal = tk.Text(terminal_wrap, bg="#ffffff", fg="#18181b",
                                insertbackground="#18181b", selectbackground="#bfdbfe",
                                font=("Consolas", 10), wrap="char", undo=False,
                                borderwidth=1, relief="solid", padx=12, pady=12, state="disabled")
        scroll = ttk.Scrollbar(terminal_wrap, command=self.terminal.yview)
        self.terminal.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.terminal.pack(side="left", fill="both", expand=True)
        self.terminal.bind("<KeyPress>", self._terminal_key)
        self.terminal.bind("<<Paste>>", self._paste)
        self.terminal.bind("<Button-1>", lambda _e: self.terminal.focus_set())
        self.terminal.bind("<Button-3>", self._show_context_menu)  # Right-click context menu
        
        # Context menu for copy/paste
        self.term_menu = tk.Menu(self.terminal, tearoff=0, bg="#ffffff", fg="#18181b",
                                 activebackground="#e2e8f0", activeforeground="#18181b",
                                 font=("Segoe UI", 9))
        self.term_menu.add_command(label="📋 Kopyala", command=self._copy_terminal)
        self.term_menu.add_command(label="📥 Yapıştır", command=self._paste_to_terminal)
        self.term_menu.add_separator()
        self.term_menu.add_command(label="Tümünü Seç", command=lambda: self._select_all_terminal())

        footer = tk.Frame(self.root, bg=PANEL, height=30)
        footer.pack(fill="x", side="bottom")
        footer.pack_propagate(False)
        tk.Label(footer, text="SSH private key kullanılır • Anahtar dosyası diske kopyalanmaz",
                 bg=PANEL, fg=MUTED, font=("Segoe UI", 8)).pack(side="left", padx=12)
        self.footer_status = tk.Label(footer, text="Hazır", bg=PANEL, fg=MUTED,
                                      font=("Segoe UI", 8))
        self.footer_status.pack(side="right", padx=12)
        for entry in (self.host, self.port, self.username, self.key_path, self.cf_id, self.cf_secret):
            entry.bind("<FocusOut>", lambda _event: self._save_settings())
        self._write("FinalSSH hazır. Bağlanmak için sunucu bilgilerini girin.\n")

    def _settings_file(self):
        base = Path(os.environ.get("APPDATA", str(Path.home()))) / "FinalSSH"
        return base / "settings.json"

    def _load_settings(self):
        try:
            path = self._settings_file()
            if not path.is_file():
                return
            settings = json.loads(path.read_text(encoding="utf-8"))
            for widget, key in (
                (self.host, "host"), (self.port, "port"),
                (self.username, "username"), (self.key_path, "key_path"),
                (self.cf_id, "cloudflare_client_id"),
            ):
                value = settings.get(key)
                if value is not None:
                    widget.delete(0, "end")
                    widget.insert(0, str(value))
            self.cloudflare_enabled.set(bool(settings.get("cloudflare_enabled", False)))
            self._mode_changed()
        except Exception as exc:
            self._write(f"[Ayarlar yüklenemedi: {exc}]\\n")

    def _save_settings(self):
        try:
            path = self._settings_file()
            path.parent.mkdir(parents=True, exist_ok=True)
            settings = {
                "host": self.host.get().strip(),
                "port": self.port.get().strip(),
                "username": self.username.get().strip(),
                "key_path": self.key_path.get().strip(),
                "cloudflare_enabled": bool(self.cloudflare_enabled.get()),
                "cloudflare_client_id": self.cf_id.get().strip(),
            }
            temp_path = path.with_suffix(".tmp")
            temp_path.write_text(json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8")
            temp_path.replace(path)
        except Exception as exc:
            self._write(f"[Ayarlar kaydedilemedi: {exc}]\\n")

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
        if self.cloudflare_enabled.get():
            self.cf_frame.pack(fill="x", pady=(8, 0), before=self.connect_btn)
        else:
            self.cf_frame.pack_forget()
        self._save_settings()

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

    def _copy_terminal(self):
        try:
            text = self.terminal.get("1.0", "end-1c")
            if text.strip():
                self.root.clipboard_clear()
                self.root.clipboard_append(text)
                self.footer_status.configure(text="Terminal kopyalandı")
            else:
                self.footer_status.configure(text="Kopyalanacak metin yok")
        except Exception as exc:
            self.footer_status.configure(text=f"Kopyalama hatası: {exc}")

    def _paste_to_terminal(self):
        """Paste clipboard content to terminal/SSH"""
        if not self.connected or not self.channel:
            self.footer_status.configure(text="Bağlantı yok - yapıştırılamaz")
            return
        try:
            text = self.root.clipboard_get()
            if text:
                self.channel.send(text.encode("utf-8"))
                self.footer_status.configure(text="Yapıştırıldı")
            else:
                self.footer_status.configure(text="Panoda metin yok")
        except Exception as exc:
            self.footer_status.configure(text=f"Yapıştırma hatası: {exc}")

    def _show_context_menu(self, event):
        """Show right-click context menu"""
        try:
            self.term_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.term_menu.grab_release()

    def _select_all_terminal(self):
        """Select all text in terminal"""
        self.terminal.configure(state="normal")
        self.terminal.tag_add("sel", "1.0", "end-1c")
        self.terminal.configure(state="disabled")

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
        self._save_settings()
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
        mode = "Cloudflare Tunnel" if self.cloudflare_enabled.get() else "Normal SSH"
        cf_id = self.cf_id.get().strip() if mode == "Cloudflare Tunnel" else ""
        cf_secret = self.cf_secret.get().strip() if mode == "Cloudflare Tunnel" else ""
        cf_http2 = self.cf_http2.get() if mode == "Cloudflare Tunnel" else True
        cf_no_tls_verify = self.cf_no_tls_verify.get() if mode == "Cloudflare Tunnel" else False
        cf_proxy_http = self.cf_proxy_http.get().strip() if mode == "Cloudflare Tunnel" else ""
        cf_proxy_https = self.cf_proxy_https.get().strip() if mode == "Cloudflare Tunnel" else ""
        self.connect_btn.configure(state="disabled")
        self._set_status("● Bağlanıyor...", ACCENT)
        self._write(f"\n[{host}:{port}] {mode} bağlantısı kuruluyor...\n")
        threading.Thread(target=self._connect_worker,
                         args=(host, port, user, key_path, mode, cf_id, cf_secret, cf_http2, cf_no_tls_verify, cf_proxy_http, cf_proxy_https), daemon=True).start()

    def _start_cloudflare_tunnel(self, host, cf_id, cf_secret, cf_http2=True, cf_no_tls_verify=False, cf_proxy_http="", cf_proxy_https=""):
        if bool(cf_id) != bool(cf_secret):
            raise RuntimeError("Access Client ID ve Client Secret birlikte girilmelidir.")
        if not host or any(ch.isspace() for ch in host) or host.startswith("-"):
            raise RuntimeError("Cloudflare hostname alanına yalnızca hostname girin (ör. ssh.example.com).")

        library = load_cloudflared_dll()
        init_result = library.CloudflaredInit()
        if init_result != 0:
            raise RuntimeError(f"Cloudflare DLL başlatılamadı (CloudflaredInit={init_result}).")

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as reservation:
            reservation.bind(("127.0.0.1", 0))
            local_port = reservation.getsockname()[1]

        env_names = ("TUNNEL_SERVICE_TOKEN_ID", "TUNNEL_SERVICE_TOKEN_SECRET")
        env_backup = {name: os.environ.get(name) for name in env_names}
        proxy_backup = {}
        
        # Proxy ayarları
        if cf_proxy_http:
            proxy_backup["HTTP_PROXY"] = os.environ.get("HTTP_PROXY")
            os.environ["HTTP_PROXY"] = cf_proxy_http
        if cf_proxy_https:
            proxy_backup["HTTPS_PROXY"] = os.environ.get("HTTPS_PROXY")
            os.environ["HTTPS_PROXY"] = cf_proxy_https

        runtime = {"dll": library, "socket": None, "env_backup": env_backup, "proxy_backup": proxy_backup, "port": local_port}

        try:
            for name in env_names:
                os.environ.pop(name, None)
            if cf_id and cf_secret:
                os.environ["TUNNEL_SERVICE_TOKEN_ID"] = cf_id
                os.environ["TUNNEL_SERVICE_TOKEN_SECRET"] = cf_secret

            # Build command with options
            command_parts = [
                "cloudflared access ssh",
                f"--hostname {host}",
                f"--url 127.0.0.1:{local_port}",
                "--loglevel error"
            ]
            if cf_http2:
                command_parts.append("--protocol http2")
            if cf_no_tls_verify:
                command_parts.append("--no-tls-verify")
            
            command = " ".join(command_parts)
            run_result = library.CloudflaredRun(command.encode("utf-8"))
            if run_result != 0:
                raise RuntimeError(f"Cloudflare DLL komutu başlatılamadı (CloudflaredRun={run_result}).")

            deadline = time.monotonic() + 30
            last_error = None
            while time.monotonic() < deadline:
                try:
                    local_socket = socket.create_connection(("127.0.0.1", local_port), timeout=0.5)
                    local_socket.settimeout(45)
                    runtime["socket"] = local_socket
                    return runtime
                except OSError as exc:
                    last_error = exc
                    time.sleep(0.2)

            detail = f": {last_error}" if last_error else ""
            raise RuntimeError("Cloudflare DLL yerel SSH yönlendiricisini 30 saniye içinde başlatamadı" + detail)
        except Exception:
            self._stop_cloudflare_runtime(runtime)
            raise

    def _stop_cloudflare_runtime(self, runtime):
        if not runtime:
            return
        local_socket = runtime.get("socket")
        if local_socket:
            try:
                local_socket.close()
            except Exception:
                pass
        library = runtime.get("dll")
        if library:
            try:
                library.CloudflaredStop()
            except Exception:
                pass
        for name, previous_value in (runtime.get("env_backup") or {}).items():
            try:
                if previous_value is None:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = previous_value
            except Exception:
                pass
        for name, previous_value in (runtime.get("proxy_backup") or {}).items():
            try:
                if previous_value is None:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = previous_value
            except Exception:
                pass

    def _connect_worker(self, host, port, user, key_path, mode="Normal SSH", cf_id="", cf_secret="", cf_http2=True, cf_no_tls_verify=False, cf_proxy_http="", cf_proxy_https=""):
        client = paramiko.SSHClient()
        known = Path.home() / ".finalssh" / "known_hosts"
        if known.exists():
            client.load_host_keys(str(known))
        client.set_missing_host_key_policy(TrustOnFirstUse(self._ask_host_key))
        cf_runtime = None
        try:
            if mode == "Cloudflare Tunnel":
                cf_runtime = self._start_cloudflare_tunnel(host, cf_id, cf_secret, cf_http2, cf_no_tls_verify, cf_proxy_http, cf_proxy_https)
                self.events.put(("output", f"[Cloudflare DLL] Yerel güvenli yönlendirici 127.0.0.1:{cf_runtime['port']} hazır.\\n"))
                client.connect(hostname=host, port=port, username=user,
                               key_filename=key_path, sock=cf_runtime["socket"],
                               timeout=45, banner_timeout=45, auth_timeout=25,
                               look_for_keys=True, allow_agent=True)
            else:
                client.connect(hostname=host, port=port, username=user,
                               key_filename=key_path, timeout=12, banner_timeout=12,
                               auth_timeout=15, look_for_keys=True, allow_agent=True)
            channel = client.invoke_shell(term="xterm-256color", width=120, height=32)
            channel.settimeout(0.0)
            self.events.put(("connected", client, channel, host, user, cf_runtime))
        except Exception as exc:
            client.close()
            self._stop_cloudflare_runtime(cf_runtime)
            self.events.put(("error", f"Bağlantı kurulamadı: {exc}"))

    def _process_events(self):
        try:
            while True:
                event = self.events.get_nowait()
                kind = event[0]
                if kind == "connected":
                    _, self.client, self.channel, host, user, self.cf_runtime = event
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
        self._stop_cloudflare_runtime(self.cf_runtime)
        self.cf_runtime = None
        self.connected = False
        self.connect_btn.configure(state="normal")
        self.disconnect_btn.configure(state="disabled")
        self._set_status("● Bağlı değil", MUTED)
        self.footer_status.configure(text="Hazır")
        self._write(f"\n[{message}]\n")

    def _schedule_update_check(self):
        if self.closing:
            return
        self._check_for_update_async()
        self.root.after(2 * 60 * 1000, self._schedule_update_check)

    def _check_for_update_async(self, manual=False):
        if self._update_check_running or getattr(self.root, "_update_running", False):
            return
        self._update_check_running = True

        def worker():
            update = None
            available = False
            error = None
            try:
                update = check_for_update()
                available = bool(update.get("available"))
            except Exception as exc:
                error = str(exc)

            def apply():
                self._update_check_running = False
                self._update_available = available
                if self._update_button is not None:
                    self._update_button.configure(
                        text="Güncelle",
                        state="normal" if available else "disabled"
                    )
                if self._update_build_label is not None:
                    if available and update:
                        version = str(update.get("version") or "").strip().lstrip("vV")
                        self._update_build_label.configure(
                            text=f"Yeni: v{version}" if version else "Yeni sürüm mevcut",
                            state="normal"
                        )
                    else:
                        self._update_build_label.configure(text="", state="disabled")
                if self._manual_update_button is not None:
                    self._manual_update_button.configure(state="normal")
                if manual:
                    if error:
                        messagebox.showerror("Güncelleme denetimi", error, parent=self.root)
                    elif not available:
                        messagebox.showinfo("Güncelleme", f"FinalSSH v{VERSION} güncel.", parent=self.root)
            if not self.closing:
                self.root.after(0, apply)

        if self._manual_update_button is not None:
            self._manual_update_button.configure(state="disabled")
        if self._update_button is not None and not self._update_available:
            self._update_button.configure(text="Kontrol...", state="disabled")
        threading.Thread(target=worker, name="finalssh-update-check", daemon=True).start()

    def _manual_update_check(self):
        if self._update_check_running or getattr(self.root, "_update_running", False):
            return
        self._check_for_update_async(manual=True)

    def _start_update(self):
        if not self._update_available or getattr(self.root, "_update_running", False):
            return
        start_update(self.root, self._update_button)


    def close(self):
        self._save_settings()
        self.closing = True
        try:
            if self.client:
                self.client.close()
        except Exception:
            pass
        self._stop_cloudflare_runtime(self.cf_runtime)
        self.cf_runtime = None
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = FinalSSH(root)
    root.mainloop()
