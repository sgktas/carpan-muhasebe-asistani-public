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

## PostgreSQL şema kurulumu

`.env` içindeki `CARPAN_DATABASE_URL` değerini yalnız yerel/sunucu gizli
ortamında tanımlayın. Ardından:

```powershell
python scripts/migrate.py
```

Bu komut yalnız `platform_api/migrations/` içindeki sürümlü SQL dosyalarını
uygular. Mevcut Acki Radar veritabanına kesinlikle bağlanmamalıdır.

## Gizli bilgiler

- `.env` dosyası Git'e eklenmez.
- `CARPAN_JWT_SECRET` en az 32 bayt rastgele değer olmalıdır.
- PostgreSQL uygulama kullanıcısı yalnız `carpan` şeması için gerekli izinlere
  sahip olmalıdır.
- Finansal Excel dosyaları başlangıç sürümünde API'ye yüklenmez.
