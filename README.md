# FinalSSH

FinalSSH, Windows için tek dosyalık bir SSH masaüstü istemcisidir. Python, Tkinter ve Paramiko ile geliştirilmiştir. Normal SSH bağlantısının yanında Cloudflare Tunnel + Cloudflare Access üzerinden SSH bağlantısını da destekler.

## Özellikler

- Host/IP, port ve kullanıcı adı ile doğrudan SSH bağlantısı.
- PEM veya OpenSSH biçiminde private key ile kimlik doğrulama; SSH hesap parolasıyla giriş yoktur.
- Uygulama içi etkileşimli terminal.
- İlk bağlantıda sunucu host-key parmak izi onayı; onaylanan anahtarlar `~/.finalssh/known_hosts` konumunda saklanır.
- Tek bir **Cloudflare Tunnel kullan** kutucuğu: kapalıyken normal SSH, açıkken Cloudflare Access üzerinden SSH.
- Cloudflare Access tarayıcı tabanlı oturum açma veya Service Token (Client ID + Client Secret) desteği.
- Uygulama içinden GitHub Releases güncelleme kontrolü ve EXE güncellemesi.
- Sürüm numarası GitHub Actions tarafından otomatik oluşturulur.

## Kullanıcı için kurulum

1. [GitHub Releases](https://github.com/dincer552/Finalssh/releases/latest) sayfasından doğrudan `FinalSSH.exe` dosyasını veya ZIP içinden `FinalSSH.exe` dosyasını indirin.
   - `FinalSSH.zip` arşivinin içinde yalnızca `FinalSSH.exe` bulunur.
2. EXE'yi çift tıklayarak çalıştırın.
3. SSH sunucu bilgilerinizi ve private key dosyanızı seçin.
4. Normal SSH için Cloudflare kutucuğunu boş bırakın. Cloudflare bağlantısı için **Cloudflare Tunnel kullan** kutucuğunu işaretleyin.

**Kullanıcı bilgisayarına ayrıca Python, Paramiko, cloudflared, BAT dosyası veya başka bir Cloudflare programı kurmak gerekmez.** Resmî Windows AMD64 `cloudflared` istemcisi yayımlanan tek dosyalık EXE'nin içine paketlenir. PyInstaller tek dosya uygulamayı başlatırken bu gömülü bileşeni kendi geçici çalışma alanına açar; kullanıcıdan ayrı bir dosya seçmesi veya elle çıkarması istenmez.

## Cloudflare Tunnel ilk yapılandırması

Uygulama Cloudflare istemcisini içerir; ancak bir Cloudflare hesabı veya sunucu tarafındaki Tunnel yapılandırmasını otomatik oluşturmaz. Bu ayarlar sunucu/Cloudflare hesabı tarafında bir kez yapılmalıdır:

1. Cloudflare Zero Trust'ta bir Tunnel oluşturun ve sunucudaki SSH servisine (genellikle `localhost:22`) yönlendiren bir Public Hostname tanımlayın.
2. Bu hostname için Cloudflare Access uygulaması ve erişim politikası oluşturun.
3. FinalSSH içinde **Cloudflare Tunnel kullan** kutucuğunu işaretleyin.
4. Host/IP alanına herkese açık Access hostname'ini (ör. `ssh.example.com`) girin.
5. Linux kullanıcı adınızı ve PEM/OpenSSH private key dosyanızı seçin.
6. Tarayıcı üzerinden Access oturumu açmak için Service Token alanlarını boş bırakın. Service Auth politikası kullanıyorsanız Client ID ve Client Secret alanlarının ikisini de doldurun.

Cloudflare Tunnel'ın yayınlanan rotası hedef SSH portunu belirler (genellikle 22). Port alanı doğrudan SSH bağlantısında kullanılır. Cloudflare seçeneği açıkken bağlantı, uygulama içine gömülmüş `cloudflared` istemcisi üzerinden kurulur.

## Güvenlik notları

- SSH private key dosyası uygulama klasörüne kopyalanmaz; Paramiko'ya seçilen dosyanın yolu verilir.
- SSH sunucu parolası istenmez veya kaydedilmez.
- İlk bağlantıda sunucu anahtarının parmak izi kullanıcıya gösterilir; yalnızca onaylanırsa kaydedilir.
- Service Token bilgileri diske yazılmaz; cloudflared alt sürecine ortam değişkenleri üzerinden aktarılır, komut satırı argümanlarına eklenmez.
- Yalnızca erişim yetkiniz olan sunuculara bağlanın.

## Otomatik derleme ve sürüm yayımlama

GitHub Actions, `main` veya `master` dalına her push işleminde (ya da elle başlatıldığında) Windows EXE üretir ve sürümlü GitHub Release yayımlar.

Derleme akışı:

1. Cloudflare'ın resmî `cloudflared` GitHub Releases kaynağından Windows AMD64 istemcisini alır.
2. GitHub Releases API'sinin sağladığı SHA-256 özetiyle indirilen dosyayı doğrular. Özet uyuşmazsa derlemeyi durdurur.
3. Doğrulanan istemciyi PyInstaller kullanarak `FinalSSH.exe` içine ekler.
4. Sürüm numarasını otomatik artırır, `FinalSSH.exe` dosyasını ZIP içine alır ve hem EXE'yi hem `FinalSSH.zip` arşivini GitHub Release'e yükler.

Kullanıcıya ayrı bir `build.bat` veya Cloudflare kurulum paketi dağıtılmaz. Yerel geliştirici çalıştırması için aşağıdaki kaynak kod adımları geçerlidir; Cloudflare özelliği kaynak kod modunda çalıştırılırken sistemde `cloudflared` bulunmalıdır.

## Kaynak koddan çalıştırma

Windows PowerShell:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python main.py
```

Kaynak kod modunda doğrudan SSH için cloudflared gerekmez. Cloudflare Tunnel özelliği için resmî cloudflared istemcisini kurup PATH'e ekleyin.

## Güncelleme

Uygulamadaki **Güncellemeleri kontrol et** düğmesi GitHub'daki en son Release'i kontrol eder. Daha yeni sürüm bulunursa kullanıcı onayından sonra EXE indirilir; uygulama kapanır, dosya değiştirilir ve yeni sürüm yeniden başlatılır. Sürüm karşılaştırması sayısal bileşenlerle yapılır (ör. `0.2.10`, `0.2.9` sürümünden yenidir).

## Üçüncü taraf bileşen

FinalSSH, Cloudflare'ın resmî `cloudflared` istemcisini paketler. Dağıtım ve lisans bilgileri için [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) dosyasına ve [Cloudflare cloudflared projesine](https://github.com/cloudflare/cloudflared) bakın.
