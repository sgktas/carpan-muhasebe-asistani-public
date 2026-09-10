# Çarpan Merkezi Platform API

Bu klasör, Çarpan Muhasebe Asistanı'nın merkezi B2B katmanıdır. Masaüstü
uygulaması finansal Excel dosyalarını yerelde işlemeye devam eder; bu API ise
firma, kullanıcı, rol, lisans, cihaz ve denetim bilgisinin güvenli merkezi olur.

## İlk kapsam

- PostgreSQL üzerinde çok-firmalı veri şeması
- Firma, kullanıcı ve rol modeli
- Lisans ve cihaz aktivasyon kaydı
- Değişiklik algılayan merkezi denetim izi
- Parola özeti ve kısa ömürlü erişim belirteci altyapısı
- Nginx arkasında çalışacak FastAPI sağlık ucu

Bu temel, henüz gerçek VPS'e kurulmuş değildir. Sunucu yükseltildikten sonra
ayrı Linux kullanıcısı, ayrı PostgreSQL veritabanı ve ayrı Nginx alanı ile
dağıtılacaktır.

Lisans API'si `GET /v1/license`, cihaz aktivasyonu ise
`POST /v1/devices/activate` uçlarından çalışır. Cihaz aktivasyonunda donanım
seri numarası veya kullanıcı verisi kullanılmaz; masaüstünün ürettiği rastgele
kurulum kimliğinin tek yönlü özeti saklanır. Merkezi bağlantı devre dışıyken
masaüstü uygulaması yerel çalışmasına devam eder.

## Yerel kurulum

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn carpan_platform.main:app --reload --port 8010
```

Yerel geliştirmede API belgeleri `http://127.0.0.1:8010/docs` altında görünür.
Üretimde doğrudan internete açılmaz; Nginx ve HTTPS arkasında çalışır.
API yanıtları tarayıcı/paylaşımlı önbellek için `no-store` olarak işaretlenir;
üretimde HSTS başlığı da eklenir. Nginx, HTTPS yönlendirme ve istek hızı sınırını
tek dış sınır olarak uygular; uygulama içinde çok-sunuculu ortamda yanıltıcı bir
hafıza içi hız limiti kullanılmaz.
Yerel merkezi yönetim paneli `http://127.0.0.1:8010/admin` adresindedir.
Bu panel yalnız kullanıcı, rol, cihaz ve lisans özetlerini okur; finansal dosya
ve müşteri verisi kabul etmez.

`/health` servis sürecinin ayakta olduğunu, `/ready` ise imzalama anahtarı,
veritabanı ve tüm şema migrasyonlarının canlı çalışmaya uygun olduğunu denetler.
VPS dağıtımından hemen önce salt-okunur ön kontrol için şunu çalıştırın:

```powershell
python scripts/preflight_deployment.py
```

## Yedek doğrulama

Merkezi veritabanı için yedek alma aracı özel PostgreSQL yedeği ve yanında
değişmezlik kaydı oluşturur. Parola komut satırına veya günlük kaydına yazılmaz.
Araç var olan yedeğin üstüne yazmaz; geri yükleme ya da otomatik silme yapmaz.

```powershell
python scripts/database_backup.py --pg-bin "C:\PostgreSQL\bin"
python scripts/verify_database_backup.py --pg-bin "C:\PostgreSQL\bin" --backup "local_data\carpan_platform\backups\carpan_platform_YYYYMMDD_HHMMSS.dump"
```

VPS'te zamanlayıcı önce yedeği alacak, ardından bu ikinci doğrulamayı çalıştıracak;
harici ve şifreli kopyalama ile geri-dönüş tatbikatı ayrı dağıtım adımında eklenecek.
Tatbikat komutu gerçek merkezi veritabanına yazmaz: geçici, rastgele adlı bir
veritabanı oluşturur, yedeği yalnız oraya açar ve iş bitince o geçici veritabanını
silerek şema okunabilirliğini sınar. Açık onay olmadan çalışmaz:

```powershell
python scripts/rehearse_database_restore.py --pg-bin "C:\PostgreSQL\bin" --backup "local_data\carpan_platform\backups\carpan_platform_YYYYMMDD_HHMMSS.dump" --allow-restore-rehearsal
```

## PostgreSQL şema kurulumu

`.env` içindeki `CARPAN_DATABASE_URL` değerini yalnız yerel/sunucu gizli
ortamında tanımlayın. Ardından:

```powershell
python scripts/migrate.py
```

Bu komut yalnız `platform_api/migrations/` içindeki sürümlü SQL dosyalarını
uygular. Mevcut Acki Radar veritabanına kesinlikle bağlanmamalıdır.

Migrasyon tamamlandıktan sonra ilk firma ve merkezi yönetici hesabı, yalnız
sunucu yöneticisinin açık terminalinden ve parola komut satırına yazılmadan
oluşturulur:

```powershell
python scripts/bootstrap_company.py --company-code CARPAN --company-name "Çarpan" --username admin --display-name "Platform Yöneticisi"
```

Bu komut ilk firmadan sonra tekrar çalışmaz. Sonraki firmalar, ileride eklenecek
yetkili yönetim paneli akışından oluşturulur.

## Platform sahibi yönetimi

Firma yöneticisi ile Çarpan platform sahibi farklı oturum türleridir. Platform
sahibi uçları yalnız firma/lisans/cihaz sağlığı özetini verir; müşteri, banka,
IBAN, Excel ve finansal hareket verisi taşımaz. Bu katman yalnız API
sunucusundaki `CARPAN_OWNER_DATABASE_URL` ile etkinleşir; masaüstü uygulamasına
bu bağlantı kesinlikle verilmez.

İlk platform sahibi, tüm migrasyonlar uygulandıktan sonra yalnız sunucu
terminalinde ve parolayı komut satırına yazmadan oluşturulur:

```powershell
python scripts/bootstrap_platform_operator.py --username platform.owner --display-name "Platform Sahibi"
```

Bu araç ikinci bir ilk-sahip hesabı oluşturmaz. Platform paneli arayüzü sonraki
aşamada bu ayrı oturumu kullanacaktır; şu an yalnız güvenli API sözleşmesi vardır.

Platform Merkezi (`/platform`) içinden platform sahibi:

- Yeni firma çalışma alanı, başlangıç lisansı ve ilk yönetici davetini tek
  işlemde oluşturabilir.
- İlk yönetici parolasını sistem üretmez veya saklamaz; kullanıcı tek kullanımlık
  davet bağlantısıyla kendi parolasını belirler.
- Firma lisansının planı, durumu, açık modülleri, çevrimdışı süresi ve merkezi
  zorunluluk politikası güncellenebilir.
- Firma çalışma alanı Etkin/Askıda durumuna alınabilir. Askıya alma cihaz veya
  lisans kaydını silmez; merkezi erişim doğrulaması sonraki korumalı istekte
  erişimi durdurur ve firma yeniden etkinleştirildiğinde yeniden kurulum gerekmez.

Bu işlemler platform sahibi denetim kaydına yazılır. Firma içi yönetici bu
paneli kullanamaz; platform sahibi de müşteri, banka ve finansal işlem verisine
erişemez.

Denetim kaydı kararın türünü, zamanını, uygulayan platform sahibini ve yalnız
firma kodu/durum gibi operasyon bağlamını tutar. Bu kayda müşteri, banka, IBAN,
Excel, dekont veya finansal tutar yazılmaz; panel de bu teknik bağlamı göstermez.

## Gizli bilgiler

- `.env` dosyası Git'e eklenmez.
- `CARPAN_JWT_SECRET` en az 32 bayt rastgele değer olmalıdır.
- PostgreSQL uygulama kullanıcısı yalnız `carpan` şeması için gerekli izinlere
  sahip olmalıdır.
- Finansal Excel dosyaları başlangıç sürümünde API'ye yüklenmez.
