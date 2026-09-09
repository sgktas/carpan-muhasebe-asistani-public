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
Yerel merkezi yönetim paneli `http://127.0.0.1:8010/admin` adresindedir.
Bu panel yalnız kullanıcı, rol, cihaz ve lisans özetlerini okur; finansal dosya
ve müşteri verisi kabul etmez.

`/health` servis sürecinin ayakta olduğunu, `/ready` ise imzalama anahtarı,
veritabanı ve tüm şema migrasyonlarının canlı çalışmaya uygun olduğunu denetler.
VPS dağıtımından hemen önce salt-okunur ön kontrol için şunu çalıştırın:

```powershell
python scripts/preflight_deployment.py
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

## Gizli bilgiler

- `.env` dosyası Git'e eklenmez.
- `CARPAN_JWT_SECRET` en az 32 bayt rastgele değer olmalıdır.
- PostgreSQL uygulama kullanıcısı yalnız `carpan` şeması için gerekli izinlere
  sahip olmalıdır.
- Finansal Excel dosyaları başlangıç sürümünde API'ye yüklenmez.
