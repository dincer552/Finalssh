# FinalSSH

FinalSSH, Windows için tek dosyalık bir SSH masaüstü istemcisidir. Python, Tkinter ve Paramiko ile geliştirilmiştir. Normal SSH bağlantısının yanında Cloudflare Tunnel + Cloudflare Access üzerinden SSH bağlantısını da destekler.

## Özellikler

- Host/IP, port ve kullanıcı adı ile doğrudan SSH bağlantısı.
- PEM veya OpenSSH biçiminde private key ile kimlik doğrulama; SSH hesap parolasıyla giriş yoktur.
- Uygulama içi etkileşimli terminal.
- İlk bağlantıda sunucu host-key parmak izi onayı; onaylanan anahtarlar `~/.finalssh/known_hosts` konumunda saklanır.
- Tek bir **Cloudflare Tunnel kullan** kutucuğu: kapalıyken normal SSH, açıkken Cloudflare Access üzerinden SSH.
- Cloudflare Access tarayıcı tabanlı oturum açma veya Service Token (Client ID + Client Secret) desteği.
- QudsLab Cloudflared DLL, Python `ctypes` üzerinden doğrudan çağrılır; ayrı `cloudflared.exe` süreci başlatılmaz.
- Uygulama içinden GitHub Releases güncelleme kontrolü ve EXE güncellemesi.
- Sürüm numarası GitHub Actions tarafından otomatik oluşturulur.

## Kullanıcı için kurulum

1. [GitHub Releases](https://github.com/dincer552/Finalssh/releases/latest) sayfasından doğrudan `FinalSSH.exe` dosyasını veya ZIP içinden `FinalSSH.exe` dosyasını indirin.
   - `FinalSSH.zip` arşivinin içinde yalnızca `FinalSSH.exe` bulunur.
2. EXE'yi çift tıklayarak çalıştırın.
3. SSH sunucu bilgilerinizi ve private key dosyanızı seçin.
4. Normal SSH için Cloudflare kutucuğunu boş bırakın. Cloudflare bağlantısı için **Cloudflare Tunnel kullan** kutucuğunu işaretleyin.

**Kullanıcı bilgisayarına ayrıca Python, Paramiko, `cloudflared.exe`, DLL veya başka bir Cloudflare programı kurmak gerekmez.** QudsLab projesinin Windows AMD64 Cloudflared DLL'si tek dosyalık EXE'nin içine paketlenir. PyInstaller başlatma sırasında DLL'yi kendi özel geçici çalışma alanına çıkarır ve Python `ctypes` ile yükler; kullanıcı ayrı bir dosya görmez veya elle çıkarmaz.

## Cloudflare Tunnel ilk yapılandırması

Uygulama Cloudflare istemcisini içerir; ancak bir Cloudflare hesabı veya sunucu tarafındaki Tunnel yapılandırmasını otomatik oluşturmaz. Bu ayarlar sunucu/Cloudflare hesabı tarafında bir kez yapılmalıdır:

1. Cloudflare Zero Trust'ta bir Tunnel oluşturun ve sunucudaki SSH servisine (genellikle `localhost:22`) yönlendiren bir Public Hostname tanımlayın.
2. Bu hostname için Cloudflare Access uygulaması ve erişim politikası oluşturun.
3. FinalSSH içinde **Cloudflare Tunnel kullan** kutucuğunu işaretleyin.
4. Host/IP alanına herkese açık Access hostname'ini (ör. `ssh.example.com`) girin.
5. Linux kullanıcı adınızı ve PEM/OpenSSH private key dosyanızı seçin.
6. Tarayıcı üzerinden Access oturumu açmak için Service Token alanlarını boş bırakın. Service Auth politikası kullanıyorsanız Client ID ve Client Secret alanlarının ikisini de doldurun.

Cloudflare Tunnel'ın yayınlanan rotası hedef SSH portunu belirler (genellikle 22). Port alanı SSH sunucusunun portudur. Cloudflare seçeneği açıkken gömülü DLL, `access ssh` komutunu uygulama süreci içinde çalıştırır ve yalnızca `127.0.0.1` üzerinde geçici bir yerel TCP dinleyicisi açar. Paramiko bu yerel sokete bağlanır; SSH trafiği Cloudflare Access üzerinden taşınır.

## Güvenlik notları

- SSH private key dosyası uygulama klasörüne kopyalanmaz; Paramiko'ya seçilen dosyanın yolu verilir.
- SSH sunucu parolası istenmez veya kaydedilmez.
- İlk bağlantıda sunucu anahtarının parmak izi kullanıcıya gösterilir; yalnızca onaylanırsa kaydedilir.
- Service Token bilgileri diske yazılmaz ve komut satırı argümanlarına konmaz; DLL çalışırken yalnızca uygulama sürecinin ortam değişkenlerinde tutulur ve tünel durdurulduğunda önceki ortam değerleri geri yüklenir.
- Yerel yönlendirici sadece `127.0.0.1` adresinde dinler; LAN veya genel ağa açılmaz.
- Yalnızca erişim yetkiniz olan sunuculara bağlanın.

## Otomatik derleme ve sürüm yayımlama

GitHub Actions, `main` veya `master` dalına her push işleminde (ya da elle başlatıldığında) Windows EXE üretir ve sürümlü GitHub Release yayımlar.

Derleme akışı:

1. QudsLab / Cloudflared projesinin sabitlenmiş Windows AMD64 DLL sürümünü indirir.
2. İndirilen DLL'nin SHA-256 özetini doğrular; uyuşmazlıkta derlemeyi durdurur.
3. DLL dışa aktarımlarını Windows üzerinde `ctypes` ile yükleyip başlatma/durdurma smoke testini çalıştırır.
4. Doğrulanan DLL'yi PyInstaller ile `FinalSSH.exe` içine ekler.
5. Sürüm numarasını otomatik artırır, `FinalSSH.exe` dosyasını ZIP içine alır ve hem EXE'yi hem `FinalSSH.zip` arşivini GitHub Release'e yükler.

Actions çalıştırması ayrıca `FinalSSH-<version>` adlı ZIP artifact'i üretir. Kullanıcıya ayrı bir `cloudflared.exe`, DLL veya kurulum paketi dağıtılmaz.

## Cloudflare DLL kaynağı

FinalSSH, [QudsLab / Cloudflared](https://github.com/QudsLab/Cloudflared) projesinin C uyumlu DLL API'sini kullanır. Python, `CloudflaredInit`, `CloudflaredRun` ve `CloudflaredStop` fonksiyonlarını `ctypes` üzerinden çağırır. Bağlantı, `access ssh --url 127.0.0.1:<port>` yerel dinleyicisi üzerinden Paramiko'ya aktarılır.

Kaynak modunda çalıştırmak için Windows AMD64 `cloudflared-windows-amd64.dll` dosyasını `vendor/` klasörüne koyun. Dağıtım EXE'sinde DLL zaten gömülüdür.


## Kaynak koddan çalıştırma

Windows PowerShell:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python main.py
```

Kaynak kod modunda doğrudan SSH için Cloudflare DLL gerekmez. Cloudflare Tunnel özelliğini geliştirme ortamında denemek için QudsLab DLL'sini `vendor/cloudflared-windows-amd64.dll` konumuna koyun.

## Güncelleme

FinalSSH, açıldıktan 2 saniye sonra GitHub Releases üzerindeki en son sürümü arka planda kontrol eder; uygulama açık kaldığı sürece bu kontrol 2 dakikada bir tekrarlanır. Başlık alanında:

- **Denetle:** Kullanıcının istediği anda sürüm kontrolünü başlatır.
- **Güncelle:** Yalnızca daha yeni bir sürüm bulunduğunda etkinleşir.
- **Yeşil sürüm bilgisi:** Yeni sürüm varsa `Yeni: v0.2.x` biçiminde gösterilir.

Güncelleme, TEST KONTROL uygulamasındaki gibi 2 MiB'lık küçük parçalar halinde indirilir. Her parça boyut kontrolüyle ve yeniden deneme desteğiyle alınır; parçalar birleştirilince toplam dosya boyutu doğrulanır. İndirme sırasında yüzde, indirilen/toplam MB ve hız pencere başlığında gösterilir.

İndirme tamamlandığında geçici bir PowerShell betiği çalışan uygulamanın kapanmasını bekler, yeni EXE'yi mevcut dosyanın yerine koyar ve FinalSSH'yi otomatik yeniden başlatır. Kullanıcıya BAT dosyası oluşturulmaz veya gösterilmez.



## Üçüncü taraf bileşen

FinalSSH, QudsLab / Cloudflared projesinin Windows AMD64 DLL sürümünü paketler. Ayrıntılar ve lisans bilgileri için [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) ve [Apache-2.0 lisansı](THIRD_PARTY_LICENSES/Apache-2.0.txt) dosyalarına bakın.
