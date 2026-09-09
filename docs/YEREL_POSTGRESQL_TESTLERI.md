# İzole PostgreSQL doğrulaması

Bu ortam yalnız geliştirme/test içindir. Masaüstü uygulamasını PostgreSQL'e
bağlamaz, gerçek müşteri verisi kullanmaz, Windows servisi kurmaz ve VPS'ye
erişmez. Uygulamanın mevcut yerel çalışma biçimi değişmez.

## Yerelde çalıştırma

Python ve `platform_api/requirements.txt` bağımlılıkları gereklidir. PostgreSQL
17'nin güvenilir Windows taşınabilir dağıtımındaki `bin` klasörünü kullanın.
Bu çalışma için PostgreSQL 17.11 kullanıldı. Dağıtım yalnız
`local_data/postgresql_test_runtime/17.11/pgsql` altında bulunur; Git'e veya
kaynak/EXE paketine eklenmez.

Kaynak depo klasöründen:

```powershell
py -3 platform_api/scripts/test_local_postgres.py --bin local_data/postgresql_test_runtime/17.11/pgsql/bin
```

Tüm masaüstü ve API testlerini de aynı turda çalıştırmak için sona `--all`
ekleyin. Başlatıcı:

1. İşletim sisteminin geçici klasöründe yeni bir test kümesi oluşturur.
2. Rastgele parola, SCRAM kimlik doğrulaması ve yalnız `127.0.0.1` dinleme
   adresi kullanır. Sistem PostgreSQL bağlantı ayarlarını kullanmaz.
3. Uygun bir geçici port seçer; başlatma başarısızsa başka sunucuya bağlanmaz.
4. Test sonunda kendi başlattığı kümeyi kapatır; hata durumunda da kapatmayı
   dener. Normal kullanımdaki PostgreSQL süreçlerine müdahale etmez.
5. Tanılama günlüklerinin bulunduğu geçici klasörü bildirir. Kapanmış test
   kümesi günlüklerle birlikte kalır; kendi başına sürekli çalışan servis yoktur.

Windows'ta PostgreSQL başlangıcı Türkçe kurulum yolunu yanlış yorumlayabildiği
için yürütülebilir dosyalarda mevcut kısa yol karşılığı, veri klasöründe geçici
konum kullanılır. Test çıktıları UTF-8'dir. Başlatıcı indirme yapmaz ve kalıcı
sistem ayarı değiştirmez.

Resmi dağıtım kaynakları: [PostgreSQL Windows](https://www.postgresql.org/download/windows/),
[EDB taşınabilir dosyalar](https://www.enterprisedb.com/download-postgresql-binaries).
SCRAM ve başlangıç seçenekleri: [initdb belgesi](https://www.postgresql.org/docs/17/app-initdb.html).

## Kalıcı yerel platform geliştirme ortamı

Merkezi platform geliştirmesi için test kümesinden ayrı, kalıcı ancak yalnız
bu bilgisayarda çalışan bir PostgreSQL kümesi kullanılabilir. Bu küme de
Windows hizmeti, güvenlik duvarı kuralı veya uzak erişim oluşturmaz; yalnız
`127.0.0.1` üzerinde rastgele bir port dinler.

İlk hazırlık yalnız bir kez yapılır:

```powershell
py -3 platform_api/scripts/initialize_local_platform.py --bin local_data/postgresql_test_runtime/17.11/pgsql/bin
```

Parolalar ve bağlantı bilgileri yalnız Git dışındaki
`local_data/carpan_platform/platform.env` dosyasına yazılır ve ekrana
basılmaz. Ardından API'yi yerelde çalıştırmak için:

```powershell
powershell -ExecutionPolicy Bypass -File platform_api/scripts/start_local_api.ps1
```

Sağlık kontrolü tarayıcıdan `http://127.0.0.1:8010/health`, yerel yönetim
paneli ise `http://127.0.0.1:8010/admin` adresinde görünür. Panelde firma
kodu, merkezi kullanıcı adı ve parola ile giriş yapılır; tarayıcı oturumu
kapatıldığında erişim belirteci silinir. API'yi durdurmak için aynı pencereye
`Ctrl+C` yeterlidir; PostgreSQL verisi korunur. İlk firma ve yönetici hesabı, marka/firma bilgileri netleştiğinde
ayrı bir yönetim adımıyla oluşturulur; bu işlemde parola yalnız yerel terminale
girilir.

Örnek ilk firma/yönetici oluşturma komutu aşağıdadır. Komut iki kez güvenli
parola istemi açar; parolayı komuta eklemeyin ve paylaşmayın:

```powershell
powershell -ExecutionPolicy Bypass -File platform_api/scripts/bootstrap_local_company.ps1 `
  -CompanyCode CARPAN -CompanyName "Çarpan Muhasebe Asistanı" `
  -Username admin -DisplayName "Platform Yöneticisi"
```

Bu adım yalnız ilk firma için çalışır. Bir firma zaten varsa araç hiçbir kaydı
değiştirmeden durur.

## Testlerin güvenlik sınırı

- Testler yalnız açıkça tanımlanan `CARPAN_TEST_PG_ADMIN_DSN` üzerinden, `127.0.0.1`
  ve `postgres` bakım veritabanına bağlanır. Üretim `CARPAN_DATABASE_URL` kullanılmaz.
- Rastgele isimli `carpan_test_*` veritabanı ve ona özel uygulama rolü oluşturulur.
  Test sonunda yalnız burada oluşturulan veritabanı/rol kaldırılır.
- Şema sahibi bağlantısı sadece kurulum ve sentetik veri hazırlığı içindir.
  İş akışları SUPERUSER/BYPASSRLS/CREATEDB/CREATEROLE olmayan ayrı rol ile çalışır.
- Şema sahibi RLS'yi aşabileceği için firma izolasyonu onunla test edilmez.
- Geçici parolalar oluşturulur; gerçek parolalar kullanılmaz. Test bağlamı hata
  gösteriminde bağlantı/parola ayrıntılarını gizler.
- Veritabanı sorgularının ve test sürecinin zaman sınırı vardır.

## Doğrulanan davranışlar

- Sürümlü migration dosyaları gerçek PostgreSQL'e uygulanır; ikinci çalıştırma
  aynı migration'ları tekrar uygulamaz. Mevcut dosya kontrol değerleri korunur.
- Firma bağlamı yokken şirket/üyelik/lisans/kullanıcı satırları görünmez.
- Bir firma başka firmanın kullanıcısını okuyamaz veya giriş sayacını değiştiremez.
- Firma dışına lisans yazma reddedilir; güncelleme diğer firmayı etkilemez.
- Diğer firmanın cihaz, oturum, üyelik ve denetim satırları görünmez.
- Başarısız ve bulunamayan kullanıcı girişlerinin denetim kayıtları kalıcıdır.
- Beş yanlış parola kilit oluşturur; kilitliyken doğru parola da reddedilir;
  kilit süresi dolduğunda geçerli giriş mümkündür.
- Sekiz eşzamanlı yanlış girişte sayaç kaybı ve denetim zincirinde dallanma olmaz.
- Aynı yenileme anahtarını eşzamanlı tüketen iki istekten yalnız biri başarılıdır.
- Beklenmeyen hata işlemdeki değişiklikleri geri alır; uygulama rolü şema oluşturamaz.

Son madde grupları bütün merkezi güvenliği tamamlamaz. Anahtar tüketimi ile
yenisinin oluşturulmasının tek atomik işlem haline getirilmesi, cihaz iptali,
lisans yetkileri, API yetki kontrolleri, yedekten dönüş ve üretim ağ yapılandırması
ayrıca ele alınmalıdır.

## GitHub kontrolü

`Tests` iş akışındaki `postgres-integration` işi ayrı PostgreSQL 17.11 servisi
kullanır. Sabit CI parolası yalnız bu geçici servise aittir; üretimde kullanılmaz.
Bağlantı eksikse bu iş atlanmaz, başarısız olur. Normal birim test çalıştırmasında
PostgreSQL seçilmemişse gerçek veritabanı testleri açıklamayla atlanır.

İş akışının dosyasını hazırlamak GitHub'da çalıştığını kanıtlamaz. Gönderimden
sonra uzak çalıştırma sonucu ayrıca kontrol edilmelidir.
