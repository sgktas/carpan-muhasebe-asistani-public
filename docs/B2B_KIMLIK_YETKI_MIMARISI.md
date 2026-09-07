# B2B Kimlik, Yetki ve Denetim Mimarisi

## Amaç

Masaüstü uygulamasındaki anonim kullanıcı adı girişini, firma bağlamı bulunan
parolalı oturum ve rol tabanlı erişim modeliyle değiştirmek. Bu katman gelecekteki
sunucu tabanlı lisans, çoklu firma, onay akışı ve merkezi yönetim özelliklerinin
yerel temelidir.

## Sınırlar

- `app/core/identity.py` firma, kullanıcı, üyelik/rol, parola doğrulama ve güvenlik
  olaylarının tek karar katmanıdır.
- Arayüz parola özeti üretmez ve rol kararı vermez; yalnız `IdentityStore` ile
  `AuthenticatedSession.can()` sonuçlarını kullanır.
- Modül görünürlüğü `AuthenticatedSession.allows_module()` üzerinden belirlenir.
- Operasyon kayıtları görünen ada ek olarak `company_id` ve `user_id` taşır.
- Bu aşama yerel kurulum içindir. Bulut senkronizasyonu, merkezi lisans ve farklı
  makineler arası kullanıcı yönetimi henüz bu sözleşmenin parçası değildir.

## Roller

| Rol | Erişim |
| --- | --- |
| `ADMIN` | Tüm modüller, ayarlar, ekip ve güvenlik kayıtları |
| `OPERATOR` | Tüm operasyon modülleri ve işlem geçmişi |
| `APPROVER` | MANİM/onay iş akışı ve işlem geçmişi |
| `AUDITOR` | İşlem geçmişi ve güvenlik kayıtları |

Yeni bir ekran veya işlem eklenirken arayüzde rol adına göre `if` yazılmaz.
Önce anlamlı bir izin adı belirlenir; izin `ROLE_PERMISSIONS` içinde role bağlanır
ve karar `session.can("izin.adi")` üzerinden verilir.

## Parola güvenliği

- Parola hiçbir tabloda veya günlükte düz metin saklanmaz.
- Her kullanıcı için 32 bayt rastgele salt kullanılır.
- Özet PBKDF2-HMAC-SHA256 ve sürümlenebilir iterasyon sayısıyla üretilir.
- Karşılaştırma zamanlama farkını azaltan `hmac.compare_digest` ile yapılır.
- Başarısız girişler sayılır; eşik aşıldığında hesap geçici kilitlenir.
- Kullanıcı adı/parola/firma hatasında dışarıya tek tip hata döndürülür.

## Denetim izi

Güvenlik olayları önceki kaydın özetini içeren SHA-256 zinciriyle tutulur. Böylece
yerel veritabanındaki sonradan yapılan değişiklikler uygulama tarafından fark
edilebilir. Bu, harici imzalı/WORM denetim deposunun yerine geçmez; ticari bulut
sürümünde olayların sunucuya imzalı biçimde aktarılması sonraki güvenlik katmanıdır.

Kayda alınan ilk olaylar:

- ilk yönetici oluşturma,
- başarılı/başarısız/bloke giriş,
- çıkış,
- kullanıcı oluşturma,
- rol veya erişim değiştirme,
- parola sıfırlama.

## Veritabanı ve geçişler

Kimlik verisi `platform.sqlite3` içinde tutulur. Şema değişiklikleri doğrudan
mevcut tabloyu varsaymak yerine `schema_migrations` ile sürümlenir. Operasyon
geçmişindeki eski kayıtlar firma/kullanıcı kimliği olmadan okunmaya devam eder.

## Firma çalışma alanları

Her oturumda uygulama aktif firmaya ait ayrı bir yerel çalışma alanı kullanır.
Bu alan eşleştirme hafızası, profiller, bölge ayarları, işlem geçmişi ve günlükleri
diğer firmalardan fiziksel olarak ayırır.

Eski tek-firma kurulumu ilk girişte silinmeden firma alanına kopyalanır; özgün
dosyalar geri dönüş için yerinde kalır. Birden fazla firma zaten varsa veriyi
tahmine dayalı biçimde hiçbir firmaya aktarmak yerine yeni firma alanı boş başlar.
Kimlik veritabanı uygulama kurulumunda ortak kalır; böylece farklı firmaların
kullanıcıları aynı giriş ekranından kendi alanlarına erişebilir.
