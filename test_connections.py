#!/usr/bin/env python3
"""
FinalSSH Corporate Network Connection Test
Python ile çalıştır: python test_connections.py
"""
import socket
import ssl
import sys
import urllib.request
import urllib.error
import time

HOSTNAME = "ssh.dinceryuksek.com"
RESULTS = []

def log_ok(msg):
    print(f"✅ {msg}")
    RESULTS.append(f"OK: {msg}")

def log_fail(msg):
    print(f"❌ {msg}")
    RESULTS.append(f"FAIL: {msg}")

def test_tcp(host, port, name, timeout=5):
    try:
        sock = socket.create_connection((host, port), timeout=timeout)
        sock.close()
        log_ok(f"{name} ({host}:{port})")
        return True
    except Exception as e:
        log_fail(f"{name} ({host}:{port}) - {e}")
        return False

def test_http(url, name, timeout=10):
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'FinalSSH-Test/1.0'})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            log_ok(f"{name} - HTTP {resp.status}")
            return True
    except urllib.error.HTTPError as e:
        log_fail(f"{name} - HTTP {e.code}")
        return False
    except Exception as e:
        log_fail(f"{name} - {e}")
        return False

def test_dns(hostname):
    try:
        ips = socket.getaddrinfo(hostname, None)
        for ip in ips:
            print(f"   {hostname} → {ip[4][0]}")
        log_ok(f"DNS çözümleme ({hostname})")
        return True
    except Exception as e:
        log_fail(f"DNS çözümleme ({hostname}) - {e}")
        return False

def test_udp_quic():
    """QUIC/UDP 443 testi"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(3)
        # Cloudflare QUIC endpoint
        sock.sendto(b'\x00', ("1.1.1.1", 443))
        data, _ = sock.recvfrom(1024)
        sock.close()
        log_ok("UDP 443 (QUIC)")
        return True
    except socket.timeout:
        log_fail("UDP 443 (QUIC) - Timeout (muhtemelen engelli)")
        return False
    except Exception as e:
        log_fail(f"UDP 443 (QUIC) - {e}")
        return False

def check_proxy():
    import os
    proxy_vars = ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy']
    for var in proxy_vars:
        val = os.environ.get(var)
        if val:
            print(f"   🔧 Env Proxy ({var}): {val}")
            return True
    
    # Windows registry proxy
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, 
            r"Software\Microsoft\Windows\CurrentVersion\Internet Settings")
        proxy_enable = winreg.QueryValueEx(key, "ProxyEnable")[0]
        proxy_server = winreg.QueryValueEx(key, "ProxyServer")[0]
        winreg.CloseKey(key)
        if proxy_enable:
            print(f"   🔧 Windows Proxy: {proxy_server}")
            return True
    except:
        pass
    
    print("   Proxy algılanmadı (doğrudan bağlantı)")
    return False

print("=" * 60)
print("FinalSSH Kurumsal Ağ Bağlantı Testleri")
print("=" * 60)
print()

# 1. DNS
print("1. DNS Çözümlemesi:")
test_dns(HOSTNAME)
print()

# 2. TCP Portlar
print("2. TCP Port Testleri:")
test_tcp(HOSTNAME, 443, "Cloudflare HTTPS")
test_tcp(HOSTNAME, 80, "HTTP")
test_tcp(HOSTNAME, 22, "SSH Direct")
test_tcp("1.1.1.1", 443, "Cloudflare DNS HTTPS")
test_tcp("1.1.1.1", 53, "Cloudflare DNS")
test_tcp("8.8.8.8", 53, "Google DNS")
print()

# 3. HTTP/HTTPS
print("3. HTTP/HTTPS Erişim:")
test_http(f"https://{HOSTNAME}", "Cloudflare Access Sayfası")
test_http("https://api.cloudflare.com/client/v4/user/tokens/verify", "Cloudflare API")
test_http("https://www.cloudflare.com/cdn-cgi/trace", "Cloudflare Trace")
test_http("https://github.com", "GitHub")
print()

# 4. Cloudflare Domainleri
print("4. Cloudflare Domainleri (443):")
for domain in ["api.cloudflare.com", "dash.cloudflare.com", "cloudflareaccess.com", 
               "argotunnel.com", "trycloudflare.com", "cloudflare.com"]:
    test_tcp(domain, 443, domain)
print()

# 5. Proxy
print("5. Proxy Algılama:")
check_proxy()
print()

# 6. QUIC/UDP
print("6. QUIC/UDP Test:")
test_udp_quic()
print()

# Özet
print("=" * 60)
print("ÖZET:")
for r in RESULTS:
    status = "✅" if r.startswith("OK") else "❌"
    print(f"  {status} {r}")
print()
print("YORUMLAMA:")
print("  • HTTPS (443) kapalı → Firewall engelliyor")
print("  • UDP 443 engelli → QUIC engelli, --protocol http2 gerekli")
print("  • Cloudflare domainleri engelli → IT'e allowlist isteyin")
print("  • Proxy varsa → FinalSSH'e proxy desteği eklenmeli")
