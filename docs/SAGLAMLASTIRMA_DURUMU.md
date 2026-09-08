# Sağlamlaştırma çalışma durumu

## Güncel durum — 8 Eylül 2026, gerçek PostgreSQL adımı

- İzole PostgreSQL 17.11 ortamı hazırlandı; sistem servisi veya VPS kurulmadı.
- Gerçek testler `users` tablosundaki firma filtresi eksikliğini yakaladı:
  önce 2 başarısız / 9 başarılı test. `0003_users_tenant_scope.sql` ile
  üyelik üzerinden kullanıcı RLS politikası eklendi. Önceki migration'lar
  değiştirilmedi.
- Kapsam genişletildi: 17 gerçek PostgreSQL testi; tüm uygulamayla birlikte
  280 başarılı test. Beş giriş kilidi, sekiz eşzamanlı giriş, firma sınırları,
  denetim zinciri ve anahtarın tek kullanımlık tüketimi doğrulandı.
- GitHub için ayrı PostgreSQL işi eklendi; henüz gönderilmedi/uzakta çalıştırılmadı.
- Test sunucusu turların sonunda kapandı. Orijinal şablonlara, müşteri verilerine
  ve mevcut uygulama veritabanlarına dokunulmadı.
- Ayrıntılı çalışma ve doğrulama sınırları `YEREL_POSTGRESQL_TESTLERI.md` içindedir.

Sıradaki öncelik merkezi oturumun sunucu/firma/kullanıcı bağlamı; ardından
işlem geçmişi sahipliği ve çıktı üretiminde zorunlu şablon doğrulamasıdır.
Atomik anahtar yenileme, cihaz/lisans yetkileri ve geri yükleme hâlâ tamamlanmış
sayılmamalıdır.

## 8 Eylül 2026 — İlk küçük adım

Tamamlananlar:

- Merkezi hesap ekranı, düğmeleri oluşturmadan durum yenilemesi yapmıyor.
  Oturum bulunan ve bulunmayan açılış senaryoları test edildi.
- Merkezi giriş reddi, başarısız deneme sayacı ve denetim kaydının bulunduğu
  işlem tamamlandıktan sonra yükseltiliyor. Beklenmeyen depolama hataları
  hâlâ işlemi geri alıyor.
- Kullanıcı sayacının eşzamanlı güncellemeleri için `FOR UPDATE OF u` eklendi.
  Kilit süresi değerlendirmesi satır kilidi alındıktan sonraki saati kullanıyor.
- 8 yeni test eklendi. Düzeltme öncesi 7 hata, 1 başarı; düzeltme sonrası
  8 başarı. Tüm mevcut testlerle birlikte 262 test başarılı.

Bu ilk adımın o andaki doğrulama sınırı (sonraki PostgreSQL sonucu yukarıda):

- Merkezi veritabanı testleri işlem sınırını taklit eder; gerçek PostgreSQL
  kilitlemesini, RLS rollerini veya canlı sunucuyu doğrulamaz.
- Ekranın ağ çağrıları henüz arka plan işine taşınmadı. Açılış sırası hatasının
  çözülmesi, yavaş ağda arayüzün donmayacağı anlamına gelmez.
- Bu adımda Netsis/FOM şablonları, çıktı kodu, müşteri verileri veya VPS
  değiştirilmedi. Paketleme ve GitHub gönderimi yapılmadı.

İlk adımda belirlenen iş sırası (1. madde yukarıdaki kapsamda tamamlandı):

1. İzole PostgreSQL ortamında başarısız girişlerin kalıcılığı, beş deneme
   kilidi, eşzamanlı giriş ve gerçek çalışma rolü/RLS testleri.
2. Merkezi oturumun sunucu/firma/kullanıcı bağlamına bağlanması; sunucu
   değişikliğinde eski anahtarın yeni sunucuya gönderilmesinin engellenmesi.
3. İşlem geçmişinde firma kontrollü yazma, durum geçişi ve aktif iş sahipliği.
4. Orijinal şablon onay kontrolünün her çıktı üretiminde zorunlu kapı olması.
5. Merkezi ağ işlemlerinin güvenli arka plan yürütücüsüne taşınması.

Bu liste bütün mimarinin tamamlandığını ifade etmez. Lisans/cihaz bağlantısı,
atomik oturum yenileme, kalıcı finansal dağıtım kayıtları, yedekten dönüş ve
gerçek ERP kabul testleri sonraki sağlamlaştırma kapsamındadır.
