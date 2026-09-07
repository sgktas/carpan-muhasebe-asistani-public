# Merkezi Platform API Mimarisi

## Amaç

`platform_api`, Çarpan'ın masaüstü uygulamasından bağımsız merkezi B2B servisidir.
İlk sürümde merkezde yalnız kimlik, firma, rol, lisans, cihaz ve denetim bilgisi
tutulur. Banka hareketleri, müşteri listeleri ve Netsis çıktıları müşterinin
bilgisayarında kalır.

## Katmanlar

```text
Masaüstü uygulaması ── HTTPS ──> platform_api ──> PostgreSQL
Web yönetim paneli ── HTTPS ───> platform_api ──> PostgreSQL
```

Masaüstü istemcisi PostgreSQL'e doğrudan bağlanmaz. API, Nginx arkasında yalnız
HTTPS ile yayınlanır. PostgreSQL yalnız VPS içinden erişilebilir.

## Masaüstü bağlantı davranışı

Masaüstündeki Ayarlar ekranında merkezi API adresi yerel olarak kaydedilir. Adres
HTTPS olmalıdır; yalnız yerel geliştirme için `localhost` üzerinde HTTP kabul
edilir. Uygulama başlangıçta ağı beklemez. Kullanıcı "Bağlantıyı sınayın"
seçtiğinde yalnız `/health` çağrısı yapılır.

Merkez henüz kurulmamış ya da ulaşılamıyorsa masaüstü uygulaması yerel kimlik,
eşleştirme hafızası ve dosya işleme ile çalışmaya devam eder. Bu aşamada merkezi
bağlantı, lisans veya oturum verisini saklamaz ve banka/Excel/müşteri verisi
göndermez.

## Kimlik akışı

1. Kullanıcı firma kodu, kullanıcı adı ve parolayla `/v1/auth/login` çağrısı yapar.
2. API firma kodunu güvenli PostgreSQL fonksiyonuyla çözer.
3. API, firma kapsamını PostgreSQL oturumuna `app.company_id` olarak tanımlar.
4. RLS politikaları yalnız o firmaya ait üyelik, lisans, cihaz, token ve denetim
   kayıtlarını görünür kılar.
5. Başarılı girişte 15 dakikalık, firma ve rol iddiası taşıyan imzalı erişim tokenı
   üretilir.
6. İstemci `/v1/auth/me` ile tokenın geçerliliğini ve firma kapsamını doğrular.

Uzun ömürlü oturum ve cihaz yenileme tokenları veri tabanı şemasında ayrılmıştır;
yenileme/iptal uçları ikinci API diliminde uygulanacaktır.

## Yetki ilkeleri

- Token içindeki firma kimliği, istemciden gelen firma kimliği yerine geçmez;
  her veri işlemi veritabanı RLS politikasıyla yeniden sınırlanır.
- `ADMIN`, `OPERATOR`, `APPROVER`, `AUDITOR` rol adları masaüstü ve API arasında
  aynı sözleşmeyi kullanır.
- İlk merkezi firma ve yönetici hesabı açık web kaydıyla oluşturulmaz. Yalnız
  VPS üzerinde parola istemi kullanan `bootstrap_company.py` komutu kullanılır.
- Hatalı girişlerde kullanıcı/firma varlığını açığa çıkarmayan tek tip hata döner.

## Denetim izi

Merkezi giriş, kullanıcı/yetki değişikliği ve ileride lisans hareketleri
`carpan.audit_events` tablosunda firma başına hash zinciri ile kaydedilir.
Bu zincir değişikliği algılar; yedekleme ve erişim logları ayrıca tutulmalıdır.

## Dağıtım sınırı

`platform_api/.env` ve `/etc/carpan-platform/api.env` gizlidir. Gerçek bağlantı
dizeleri, token anahtarları veya müşteri verileri hiçbir zaman bu depoya, testlere,
loglara veya destek dosyalarına yazılmaz.
