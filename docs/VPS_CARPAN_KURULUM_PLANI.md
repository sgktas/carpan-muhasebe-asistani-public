# Çarpan VPS Kurulum Planı

## Mevcut durum — 7 Eylül 2026

- Sunucu: Ubuntu 24.04 LTS
- Mevcut uygulama: Acki Radar, Nginx + PM2 ile çalışıyor
- Kullanılabilir bellek: yeni veritabanı ve API için yetersiz
- Disk: yeterli
- Sunucuda PostgreSQL ve Docker kurulu değil

Acki Radar'a ait dosyalar, PM2 süreçleri, Nginx yapılandırması veya veritabanı
bu plan uygulanırken değiştirilmez.

## Kapasite kararı

- En düşük canlı ortam: 4 GB RAM
- Tercih edilen canlı ortam: 8 GB RAM
- PostgreSQL, API ve web paneli kurulmadan önce yükseltme sonrası RAM/disk tekrar
  ölçülür.

## İzolasyon sözleşmesi

| Alan | Acki Radar | Çarpan Platform |
| --- | --- | --- |
| Linux kullanıcısı | mevcut root/PM2 düzeni | `carpan` |
| Uygulama dizini | `/var/www/acki-radar` | `/var/www/carpan-platform` |
| API portu | mevcut `127.0.0.1:3000` | `127.0.0.1:8010` |
| PostgreSQL veritabanı | mevcut sistemden bağımsız | `carpan_platform` |
| Nginx alanı | Acki Radar alan adı | `api.<marka-alan-adi>` |
| Loglar | mevcut | `journalctl -u carpan-api` |

PostgreSQL portu 5432 internete açılmaz. Nginx yalnız HTTPS trafiğini kabul
eder; API yalnız `127.0.0.1:8010` üzerinden Nginx tarafından çağrılır.

## Kurulum sırası

1. VPS paketi yükseltilir; kaynaklar tekrar doğrulanır.
2. `carpan` adlı yetkisiz Linux servis kullanıcısı oluşturulur.
3. PostgreSQL kurulup yalnız yerel bağlantı dinleyecek şekilde yapılandırılır.
4. Ayrı `carpan_platform` veritabanı ile uygulama/migrasyon kullanıcıları
   oluşturulur. Acki Radar ile kullanıcı, veritabanı veya şema paylaşılmaz.
5. `/var/www/carpan-platform` altında kaynak ve sanal ortam hazırlanır.
6. `/etc/carpan-platform/api.env` yalnız sunucuda oluşturulur; Git'e konmaz.
7. Sürümlü PostgreSQL migrasyonları uygulanır.
8. İlk firma ve merkezi yönetici hesabı, parola komut satırına yazılmadan
   `bootstrap_company.py` ile oluşturulur.
9. `carpan-api.service` yalnız `127.0.0.1:8010` portunda başlatılır.
10. Alan adı kesinleştiğinde Nginx, SSL sertifikası ve `api.` alt alanı eklenir.
11. Otomatik günlük PostgreSQL yedeği ve geri-yükleme denemesi kurulur.

## Yedekleme ölçütü

- Günlük şifreli PostgreSQL dump'ı sunucu dışındaki bir hedefe gider.
- En az 14 günlük geri dönüş noktası tutulur.
- Her sürümde geri yükleme denemesi yapılarak yedek doğrulanır.
- Yerel masaüstü Excel dosyaları ilk sürümde merkezi API'ye yüklenmez.

## Uygulama anahtarları

- `CARPAN_DATABASE_URL` ve `CARPAN_JWT_SECRET` yalnız
  `/etc/carpan-platform/api.env` içinde bulunur.
- Anahtarlar terminal çıktısına, loglara, Git'e veya destek kayıtlarına yazılmaz.
- Masaüstü uygulaması PostgreSQL'e doğrudan bağlanmaz; yalnız HTTPS API kullanır.
