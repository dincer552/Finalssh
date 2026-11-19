# FinalSSH Corporate Network Connection Test
# PowerShell'de çalıştır: .\test_connections.ps1

Write-Host "=== FinalSSH Bağlantı Testleri ===" -ForegroundColor Cyan
Write-Host ""

$hostname = "ssh.dinceryuksek.com"
$results = @()

function Test-Port {
    param($host, $port, $name)
    try {
        $socket = New-Object System.Net.Sockets.TcpClient
        $result = $socket.BeginConnect($host, $port, $null, $null)
        $success = $result.AsyncWaitHandle.WaitOne(5000)
        if ($success -and $socket.Connected) {
            Write-Host "✅ $name ($host:$port) - AÇIK" -ForegroundColor Green
            $results += "$name: AÇIK"
        } else {
            Write-Host "❌ $name ($host:$port) - KAPALI/ENGELLENMIŞ" -ForegroundColor Red
            $results += "$name: KAPALI"
        }
        $socket.Close()
    } catch {
        Write-Host "❌ $name ($host:$port) - HATA: $($_.Exception.Message)" -ForegroundColor Red
        $results += "$name: HATA"
    }
}

function Test-Http {
    param($url, $name)
    try {
        $response = Invoke-WebRequest -Uri $url -TimeoutSec 10 -UseBasicParsing
        Write-Host "✅ $name - HTTP $($response.StatusCode)" -ForegroundColor Green
        $results += "$name: HTTP $($response.StatusCode)"
    } catch {
        Write-Host "❌ $name - HATA: $($_.Exception.Message)" -ForegroundColor Red
        $results += "$name: HATA"
    }
}

Write-Host "1. DNS Çözümlemesi:" -ForegroundColor Yellow
try {
    $ips = [System.Net.Dns]::GetHostAddresses($hostname)
    foreach ($ip in $ips) {
        Write-Host "   $hostname → $ip" -ForegroundColor Green
    }
    $results += "DNS: OK"
} catch {
    Write-Host "   ❌ DNS ÇÖZÜMLEME BAŞARISIZ" -ForegroundColor Red
    $results += "DNS: BAŞARISIZ"
}

Write-Host ""
Write-Host "2. Port Testleri (TCP):" -ForegroundColor Yellow
Test-Port $hostname 443 "Cloudflare HTTPS (443)"
Test-Port $hostname 80  "HTTP (80)"
Test-Port $hostname 22  "SSH Direct (22) - genelde kapalı"
Test-Port "1.1.1.1" 443 "Cloudflare DNS (1.1.1.1:443)"
Test-Port "1.1.1.1" 53  "Cloudflare DNS (53)"
Test-Port "8.8.8.8" 53  "Google DNS (53)"

Write-Host ""
Write-Host "3. HTTP/HTTPS Erişim:" -ForegroundColor Yellow
Test-Http "https://$hostname" "Cloudflare Access Sayfası"
Test-Http "https://api.cloudflare.com/client/v4/user/tokens/verify" "Cloudflare API"
Test-Http "https://www.cloudflare.com/cdn-cgi/trace" "Cloudflare Trace"
Test-Http "https://github.com" "GitHub (güncelleme için)"

Write-Host ""
Write-Host "4. Cloudflare Domainleri:" -ForegroundColor Yellow
$cfDomains = @(
    "api.cloudflare.com",
    "dash.cloudflare.com", 
    "cloudflareaccess.com",
    "argotunnel.com",
    "trycloudflare.com",
    "cloudflare.com"
)
foreach ($domain in $cfDomains) {
    Test-Port $domain 443 "$domain (443)"
}

Write-Host ""
Write-Host "5. Proxy Algılama:" -ForegroundColor Yellow
$proxy = $env:HTTP_PROXY ?? $env:HTTPS_PROXY ?? $env:http_proxy ?? $env:https_proxy
if ($proxy) {
    Write-Host "   Proxy ayarlı: $proxy" -ForegroundColor Yellow
} else {
    # Windows proxy ayarlarını kontrol et
    $regPath = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings"
    if (Test-Path $regPath) {
        $proxyEnable = Get-ItemProperty -Path $regPath -Name ProxyEnable -ErrorAction SilentlyContinue
        $proxyServer = Get-ItemProperty -Path $regPath -Name ProxyServer -ErrorAction SilentlyContinue
        if ($proxyEnable.ProxyEnable -eq 1) {
            Write-Host "   Windows Proxy: $($proxyServer.ProxyServer)" -ForegroundColor Yellow
        } else {
            Write-Host "   Windows Proxy: KAPALI" -ForegroundColor Green
        }
    }
}

Write-Host ""
Write-Host "6. QUIC/UDP Test (cloudflared default protokolü):" -ForegroundColor Yellow
try {
    $udp = New-Object System.Net.Sockets.UdpClient
    $udp.Client.ReceiveTimeout = 3000
    $ep = New-Object System.Net.IPEndPoint([System.Net.IPAddress]::Any, 0)
    $udp.Connect("1.1.1.1", 443)
    $udp.Send([byte[]]@(0), 1) | Out-Null
    Write-Host "   ✅ UDP 443 giden - Çalışıyor" -ForegroundColor Green
    $results += "UDP 443: AÇIK"
    $udp.Close()
} catch {
    Write-Host "   ❌ UDP 443 giden - ENGELLENMIŞ (QUIC çalışmaz)" -ForegroundColor Red
    $results += "UDP 443: ENGELLI"
}

Write-Host ""
Write-Host "=== ÖZET ===" -ForegroundColor Cyan
$results | ForEach-Object { Write-Host "  $_" }
Write-Host ""
Write-Host "YORUMLAMA:" -ForegroundColor Cyan
Write-Host "  • HTTPS (443) kapalıysa → Firewall engelliyor" -ForegroundColor Gray
Write-Host "  • UDP 443 engelliysa → QUIC engelli, --protocol http2 gerekli" -ForegroundColor Gray
Write-Host "  • Cloudflare domainleri engelliysa → IT'e allowlist iste" -ForegroundColor Gray
Write-Host "  • Proxy varsa → FinalSSH'e proxy desteği eklenmeli" -ForegroundColor Gray
