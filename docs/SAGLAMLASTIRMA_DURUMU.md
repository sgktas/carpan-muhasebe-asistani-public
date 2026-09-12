# Sağlamlaştırma çalışma durumu

## 12 Eylül 2026 — 3A ERP kabul matrisi: virman şablonu

- Kullanıcının Netsis'te aktarım yaptığı son hesaplar arası virman dosyası,
  yerel onaylı şablon olarak birebir sabitlendi; tek `Sheet1` sayfası ve 32
  sütun korunur.
- Çıktı sözleşmesi artık yalnız başlık, toplam ve banka kodunu değil,
  her veri hücresinin onaylı ikinci satırdaki sayı/metin biçimini de denetler.
  `Plas.Kodu` sayıya dönerse dosya başarılı sayılmaz.
- Bu yerel kabul matrisi Netsis'e otomatik bağlanmaz; hatalı Excel'in kullanıcıya
  ulaşmadan açık bir nedenle durdurulmasını sağlar.

## 11 Eylül 2026 — ERP kabul kalitesi 2A-4: mutabakat farkı takibi

- Banka Mutabakatı çıktısındaki fark özeti, Operasyon Merkezi'nde ayrıca
  görünür: devreden bakiye farkı, bakiye tutsa da açıklanamayan kayıtlar veya
  genel tutar farkı açıkça ayrılıyor.
- Nokta atışı düzeltme Excel'i ayrıntıyı yerel tutuyor; operasyon özeti yalnız
  sayısal fark ve adetleri saklıyor. 26 ilgili test geçti.

## 11 Eylül 2026 — ERP kabul kalitesi 2A-3: manuel aktarım ret nedeni

- Geçmiş İşlemler ekranında Netsis/Psoft aktarımı reddedildi seçildiğinde
  kullanıcı banka kodu, şablon, zorunlu alan, tutar/toplam, dosya biçimi veya
  aktarım ekranı ana nedenini seçiyor.
- Operasyon Merkezi Netsis ve Psoft ret sayılarını ayrı gösteriyor; takip
  satırında seçilmiş neden okunuyor. Bu yalnız yerel manuel aktarım sonucudur;
  SQL/API veya ERP bağlantısı kurulmadı.

## 11 Eylül 2026 — ERP kabul kalitesi 2A-2: FOM birlikte yayın

- FOM raporları ve ERP entegrasyon çıktıları geçici çalışma alanında üretilir;
  tüm yazımlar ve ERP sözleşmesi kontrolleri geçince sonuç klasörü yayımlanır.
- Geç tahsilat hatası artık hazırlanmış satış dosyasını yarım başarılı sonuç
  olarak bırakmaz. Eski sonuçlar, özgün dosya adları ve şablonlar korunur.
- Sentetik FOM/çıktı sözleşmesi testlerinde 20 test geçti; yazım, doğrulama ve
  taşıma hataları ile başarılı yayın doğrulandı. Gerçek Netsis/Psoft kabul
  denemesi yapılmadı.

## 11 Eylül 2026 — ERP kabul kalitesi 2A-1: MANİM aktarım ön kontrolü

- MANİM/Netsis dosyası yazılmadan önce havale satırlarının cari kodu, işlem
  tarihi, pozitif tutarı, bölgesi ve bankası doğrulanıyor.
- Toplu banka kodlu aktarımda her satırın BM kodu, o satırın bölge/banka
  ayarındaki kodla karşılaştırılıyor. Böylece Netsis'in genel "Banka Kodunu
  Kontrol Ediniz" uyarısına düşecek yanlış/boş kod, dosya oluşmadan açık
  bölge-banka-satır mesajıyla duruyor.
- Hesaplar arası virman yalnız aynı banka transferi, kaynak/hedef BM kodları,
  `G01` genel referansı ve `00` Plas.Kodu ile devam edebiliyor. Bu kontrol
  onaylı şablonu değiştirmez; dosya yazıldıktan sonraki şablon sözleşmesi
  denetimi de yerinde kalır.
- 2A'nın sonraki alt adımı FOM satış/tahsilat çıktılarının doğrulama geçmeden
  görünür klasöre yayınlanmamasıdır.

## 11 Eylül 2026 — Operasyon otomasyonu 1E ikinci teslim: tahsilat kullanım defteri

- Tahsilat raporundaki her kaynak satır dosya özeti + veri sayfası + satır
  kimliğiyle yerel firma kapsamındaki kullanım defterine bağlandı. Defterde
  müşteri adı, banka açıklaması veya dosya yolu tutulmaz.
- Gerçek MANİM aktarımı yalnız çıktı klasörü yayımlandıktan sonra kullanım
  kaydını kesinleştirir. Simülasyon bu defteri oluşturmaz veya değiştirmez.
- Kısmi eşleştirmede kullanılan tutar kaynak satırdan düşer; kalan bakiye
  sonraki eşleştirme havuzunda görünmeye devam eder. Tam tüketilen satır tekrar
  aday yapılmaz. Aynı bakiye iki gerçek işlem tarafından aşılmak istenirse
  ikinci işlem durur.
- Manuel ekranda serbest cari/tutar düzeltmesi korunur. Kullanım defterine
  yalnız önerilen tahsilat kaynak satırına güvenle bağlanabilen bölüm yazılır;
  uygulama hiçbir zaman elle girilen bir cari kod için hayali kaynak satır
  oluşturmaz.

## 11 Eylül 2026 — Operasyon otomasyonu 1E ilk teslim: yayın günlüğü

- MANİM çıktı klasörü yayımlandıktan sonra önbellek/eşleştirme/işlenmiş dosya
  kaydı bitmeden uygulama kesilirse kaynaklar `PUBLISHED` kurtarma kaydında
  tutulur. Aynı kaynaklar sessizce tekrar çalıştırılamaz.
- Operasyon Merkezi, kurtarma gereken yayınları ve ilgili çıktı klasörünü
  gösterir. Kullanıcı eski çıktının dış aktarıma gitmediğini kontrol ederek
  yeniden işlem izni verebilir; bu görünür onay eski klasörü silmez.

## 10 Eylül 2026 — Operasyon otomasyonu 1D: yan etkisiz önizleme tamamlandı

- Aktarım öncesi simülasyon, yeni seçilen müşteri listesini artık hafızaya
  almaz; dosya ve meta kaydı yalnız gerçek aktarım başarıyla tamamlandıktan
  sonra güncellenir.
- Önizleme boş bir kalıcı veri klasörü dahi oluşturmaz; çıktı, eşleştirme
  hafızası, inceleme kuyruğu ve işlenmiş dosya kaydı yazmadan karar planını
  hesaplar.
- Simülasyon özetinde banka ve bölge adları Türkçe karakter farklarından
  dolayı ayrı satırlara bölünmez.

## 10 Eylül 2026 — Operasyon otomasyonu 1B: ayar değişikliği denetimi

- Ayarlar ekranından yapılan bölge ve aktif profil değişiklikleri artık yerel
  firma çalışma alanında önceki/yeni değer, kullanıcı ve sürümle kaydedilir.
  "Ayar Değişiklik Geçmişi" ekranı bu kayıtları okunabilir biçimde gösterir.
- Aynı ayarı iki açık pencerede değiştirmeye çalışan eski pencerenin denetim
  kararı reddedilir. Ayarlar menüsünün mevcut `settings.manage` yetkisi bu
  işlemi sınırlar; yeni bir rol adı veya dağıtık UI yetki kontrolü eklenmedi.
- Onaylı Netsis/Psoft/FOM şablonları bu kayıttan değiştirilemez ve şablon
  dosyalarına dokunulmadı. FOM için yeni şablon düzenleme yolu açılmadı.
- Sıradaki bölüm kalıcı inceleme kuyruğu: birleşik banka hareketleri, atama ve
  tekrar açma işlemleri uygulama kapanınca da izlenebilir olacak.

## 10 Eylül 2026 — Operasyon otomasyonu 1C ilk teslim: inceleme kuyruğu

- İnceleme bekleyen MANİM satırları artık firma kapsamlı yerel SQLite kuyruğuna
  yazılıyor; uygulama kapanıp açılsa da açık kayıtlar kaybolmuyor.
- Kaynak dosya/satır, bölge, banka, tutar ve kısa neden korunuyor; müşteri,
  cari kodu, IBAN ve ham açıklama kuyruğa alınmıyor.
- Atama, çözme ve yeniden açma durumları geçerli durum kontrolüyle korunuyor.
- Birleşik banka hareketlerinde tek inceleme kararı altında tüm alt havale
  satırları hem Excel inceleme çıktısına hem kalıcı kuyruğa yazılıyor.
- Operasyon Merkezi'ne açık/atanmış/çözülmüş kuyruk grupları için bölge, banka,
  alt hareket sayısı ve toplam tutar görünümü eklendi. Yetkili kullanıcı seçili
  grubu üzerine alabilir, çözebilir veya yeniden açabilir.
- Kaynak doğrulama güçlendirildi: yeni gruplar dosya içeriği özeti + sayfa +
  satır kimliği taşır. Dosya değiştiğinde eski karar sessizce devam etmez.
  Grup sürümü ve durum geçişi denetim olayı, eşzamanlı açık ekranlardaki eski
  kararların birbirini ezmesini önler.

## 10 Eylül 2026 — Operasyon otomasyonu 1D ilk teslim: simülasyon özeti

- Karar kayıtlarından yan etkisiz MANİM/Netsis toplam özeti hesaplanıyor.
- Bölge ve banka kırılımında MANİM toplamı, Netsis toplamı, fark, ödeme
  onaylandı, referanslı ve inceleme tutarları gösteriliyor.
- MANİM ekranına işlem sonrası simülasyon özetini açan görsel tablo eklendi.
  Bu tablo karar planını okur; yeni çıktı, kuyruk veya tüketim kaydı oluşturmaz.
- Dosya seçimi sonrasında gerçek aktarım başlamadan çalışan önizleme düğmesi
  1D'nin sonraki alt adımıdır.
- Önizleme arka planda çalışır; aktarım öncesi ve sonrası ayar özeti/toplam
  karşılaştırması günlükte görünür. Ayar değişmiş veya toplam farklılaşmışsa
  uyarı verir, kendiliğinden aktarım yapmaz.
- Operasyon Merkezi, geçmiş aktarım işlemlerinde simülasyonla uyumlu olanları
  ve fark çıkanları ayrı sayaçlarda gösterir. Fark çıkan işlem dikkat listesine
  alınır; kullanıcı toplamları kontrol eder.
- Mevcut inceleme Excel'i ve onaylı çıktı şablonları değiştirilmedi.
- Birleşik banka hareketlerinin tek üst grup ve alt üye kimlikleri 1C'nin
  sonraki alt adımında tamamlanacak.

## 10 Eylül 2026 — GitHub PostgreSQL denetim kaydı düzeltmesi

- 1A gönderimi sonrası GitHub uygulama testleri geçti; gerçek PostgreSQL işi
  önceki platform sahibi denetim zincirinde `KeyError: 0` yakaladı. API'nin
  sözlük biçimli veritabanı satırı, tuple gibi sayısal indeksle okunuyordu.
- Son denetim özetini okuyan sorgu artık kendi satır biçimini açıkça belirler;
  API ve ilk kurulum bağlantıları aynı sözleşmeyle çalışır. İlk kurulum ve API
  satır biçimleri için iki gerçek PostgreSQL regresyon testi eklendi.
- İzole yerel PostgreSQL üzerinde 23 test geçti; test kümesi kapatıldı.
  Mevcut yerel platform veritabanına veya VPS'ye bağlanılmadı.

## 10 Eylül 2026 — Operasyon otomasyonu 1A: kullanılan ayar sürümü

- MANİM işçisi başlamadan bölge ve çözümlenmiş profil ayarları sabitlenir;
  işlem sırasında değişen ayar dosyaları devam eden işlemi etkilemez.
- Kullanılan ayarlar yerel firma/modül kapsamında içerik özetiyle sürümlenir.
  İşlem, sürüm bağlantısı ve olay günlüğü aynı veritabanı işleminde yazılır.
  Ayarı düzenleyenin denetim izi ile kullanılan ayarın kaydı farklıdır; bu
  bölüm yalnız ikincisini sağlar.
- Günlük ve geçmiş ayrıntılarında sürüm numarası görünür. Önceki işlemler
  korunur; kaynak şablon ve doğrulama değerleri değiştirilmez.
- 13 yeni testle birlikte 103 ilgili test geçti. Gerçek ERP aktarımı yapılmadı.
- Sıradaki bölüm 1B, ayar değişikliği yönetimidir. Ardından kalıcı inceleme
  kuyruğu, simülasyon ve kontrollü yeniden işleme gelir. Detaylı sıra ve kabul
  ölçütleri `OPERASYON_OTOMASYONU_MIMARISI.md` içinde sabitlendi.

## 10 Eylül 2026 — Entegrasyon kabul sağlığı

- Entegrasyonlar ekranı, Netsis ve Psoft için onaylı şablon hazırlığının yanına
  son gerçek aktarım sonucunu ekler: kabul edildi, reddedildi veya henüz sonuç
  yok. Böylece bağlantının teknik olarak tanımlı olması ile ERP'nin çıktıyı
  gerçekten kabul etmesi ayrılır.
- Bu görünüm yalnız firma kapsamındaki yerel işlem geçmişini kullanır. Excel
  içeriği, müşteri, banka, IBAN ve finansal tutar okunmaz ya da merkezi API'ye
  aktarılmaz; ekran otomatik aktarım veya otomatik onay yapmaz.

## 10 Eylül 2026 — Platform sahibi denetim zinciri

- Platform sahibi giriş, firma kurulumu, lisans ve firma durumu kararları artık
  önceki olayın SHA-256 özetiyle bağlanan tek bir sıra içinde yazılır.
- Eski olaylar sürümlü migrasyonla zincire alınır; yeni olaylar eşzamanlı iki
  yönetim işleminin zinciri çatallamaması için işlem içi kilitle yazılır.
- Zincir yalnız karar türü, sonucu ve veri-minimum operasyon bağlamını kapsar.
  Müşteri, banka, IBAN, Excel, dekont veya finansal tutar kaydedilmez.

## 10 Eylül 2026 — Çift bağlantılı dağıtım ön kontrolü

- Dağıtım ön kontrolü artık uygulama bağlantısına ek olarak platform sahibinin
  ayrı veritabanı bağlantısını ve her iki bağlantının tüm migrasyonları
  gördüğünü denetler.
- Sahip bağlantısı eksik, hatalı veya gerideyse dağıtım durur. Böylece merkezi
  platform paneli yarım yapılandırılmış halde canlıya çıkmaz.
- Bu denetim yalnız bağlantı/şema sağlığını okur; parola, bağlantı metni veya
  müşteri-finans verisini yazdırmaz.

## 10 Eylül 2026 — Merkezi API dış sınır güvenliği

- Merkezi API yanıtları `no-store`/`no-cache` ile işaretlenir; böylece giriş,
  lisans veya yönetim yanıtları tarayıcı ya da ara önbellekte tutulmaz.
- Tüm yanıtlar içerik türü, yönlendiren ve çerçeveleme koruma başlıklarını alır.
  HSTS yalnız üretimde eklenir; yerel geliştirme HTTPS'e zorlanmaz.
- İstek hızı sınırı uygulama belleğinde değil, canlıya çıkışta Nginx katmanında
  uygulanacaktır. Bu karar çoklu API sürecinde tutarsız koruma üretmez.
- Nginx için ayrı `http {}` kapsamlı sınır tanımı ve HTTPS sunucu örneği hazırdır:
  giriş uçları dakikada 10, diğer API uçları dakikada 120 temel sınır alır.
  VPS'e bağlanılmadı ve mevcut diğer proje yapılandırmaları değiştirilmedi.

## 10 Eylül 2026 — Platform firma yaşam döngüsü

- Platform sahibi, merkezi panelden firmayı Etkin veya Askıda durumuna alabilir.
  Bu karar geri alınabilir; lisans, cihaz ve firma içi veriler silinmez.
- Merkezi erişim bağımlılığı zaten firma durumunu her korumalı istekte kontrol
  ettiğinden, askıya alınan firma açık kalan istemcide de bir sonraki merkezi
  istekte erişimi kaybeder. Yeniden Etkin yapılınca yeni cihaz kurulumu gerekmez.
- İşlem yalnız ayrı platform sahibi oturumuyla yapılır ve
  `COMPANY_STATUS_UPDATED` denetim olayına yazılır. Firma yöneticisi bu kontrolü
  kullanamaz; müşteri, banka, IBAN, Excel veya tutar verisi panele taşınmaz.
- Platform denetim kaydı, hedef firma kodu ve yeni çalışma durumunu saklar;
  bu bağlam dışarıdaki özet ekrana açılmaz. Böylece bir destek vakasında karar
  izlenebilir kalır, ancak finansal veya müşteri verisi merkezi sisteme girmez.

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

## 8 Eylül 2026 — Merkezi oturum bağlama

- Merkezi oturum kaydı artık yalnız yerel firma ve kullanıcı kimliğiyle birlikte
  şifrelenmiş olarak saklanır. Eski, bağlam içermeyen kayıtlar yeniden giriş
  ister; anahtarları hiçbir yeni sunucuya gönderilmez.
- API adresi değişirse, farklı yerel kullanıcı/firma açarsa veya oturum yanıtı
  yapılandırılmış API adresiyle uyuşmazsa yenileme/çıkış isteği yapılmadan yerel
  kayıt silinir.
- Merkezi API adresi tek biçime getirilir; HTTPS dışı uzak adres, kullanıcı
  bilgisi, sorgu parametresi ve parçalı adres kabul edilmez. İstemci yönlendirme
  takip etmez; yetkilendirme veya yenileme anahtarı başka adrese taşınmaz.
- 7 yeni oturum sınırı testi eklendi. İzole PostgreSQL testleriyle birlikte tüm
  paket 287 testte başarılı. Bu adımda VPS, müşteri verisi ve onaylı Excel
  şablonları değiştirilmedi.

Sıradaki öncelik işlem geçmişinde firma kontrollü yazma, terminal durumların
yeniden yazılmasının engellenmesi ve devam eden işin gerçek sahibi/süresi ile
takibidir. Merkezi anahtar yenilemesinin atomik hale getirilmesi ayrıca kalır.

## 8 Eylül 2026 — İşlem geçmişi sahipliği

- Her başlatılan işlem artık uygulama örneği sahibi ve süreli çalışma izniyle
  kaydedilir. Yeni pencerenin veya farklı firma geçmişinin açılması, devam eden
  canlı işlemi hemen `INTERRUPTED` durumuna çekmez.
- Süresi gerçekten dolmuş devam eden işlem, kendi firma kapsamındaki sonraki
  başlangıçta kesilmiş olarak kurtarılır. Önceki sürümden sahiplik bilgisi
  olmayan devam eden kayıtlar ilk geçişte güvenle kesilmiş kabul edilir.
- Tamamlama, hata, ara olay ve çalışma sinyali yalnız kaydı başlatan uygulama
  örneği ve aynı firma tarafından yazılabilir. `SUCCESS`, `PARTIAL`, `FAILED`
  veya `INTERRUPTED` kayıt yeniden yazılamaz.
- Firma dışı yazma, terminal kaydı yeniden yazma ve süre dolmuş kayıt
  kurtarma senaryoları test edildi. Bu adımda merkezi API, VPS, müşteri verisi
  ve onaylı Excel şablonları değişmedi.

Bu aşamada sıradaki öncelik, merkezi anahtar yenilemesinin atomik hale
getirilmesidir; şablon çalışma zamanı kilidi aşağıdaki adımda tamamlandı.

## 8 Eylül 2026 — Çıktı şablonu çalışma zamanı kilidi

- Netsis ve FOM üretimi Windows'ta başlamadan önce seçilen dosyanın
  `config/local/template_checksums.json` içindeki onaylı özgün dosya olduğu
  SHA-256 ile doğrulanıyor. Şablon eksik, değiştirilmiş veya liste dışıysa
  işlem duruyor; genel Excel çıktısına sessizce düşülmüyor.
- Microsoft Excel/COM yazma yolları, orijinal dosyayı açmak yerine geçici bir
  birebir çalışma kopyası kullanıyor. Kullanıcının onaylı kaynak şablonuna veri,
  kilit veya Excel metadata değişikliği yazılmıyor.
- Public test kaynağında gerçek yerel şablon bulunmadığı için mevcut açık test
  bayrağı korunuyor; bu istisna üretim Windows kurulumunda etkin değil.
- Çalışma zamanı bütünlük kilidi ve değişmiş şablon senaryosu için regresyon
  testleri eklendi. Şablon dosyaları ve kontrol değerleri değiştirilmedi.

Bir sonraki öncelik merkezi anahtar yenilemesini atomik hale getirmek; ardından
merkezi ağ işlemlerini güvenli arka plan yürütücüsüne taşımaktır.

## 8 Eylül 2026 — Atomik merkezi oturum yenileme

- Eski yenileme anahtarının iptali ve yeni anahtarın oluşturulması
  `rotate_refresh_token` PostgreSQL fonksiyonunda tek işlem olarak yapılıyor.
  Yeni anahtar kaydı başarısız olursa eski anahtar da tüketilmiş sayılmıyor.
- Uygulama artık ikinci bir ayrı ekleme işlemi yapmıyor; sunucudan dönen yeni
  anahtar doğrudan istemci oturumuna veriliyor.
- Migrasyon sözleşmesi ve gerçek PostgreSQL akışındaki tek-kullanım testi
  korunuyor. Yeni migrasyon uygulama sürümüne dahil edildi.

## 8 Eylül 2026 — Merkezi hesap ağ çağrılarının arka plana alınması

- Merkezi hesap penceresindeki ilk oturum geri yükleme, giriş ve çıkış çağrıları
  artık Qt arka plan iş parçacığında çalışıyor. Ağ gecikmesi veya sunucu
  yanıtı masaüstü arayüzünü kilitlemiyor.
- İşlem sürerken düğmeler güvenli biçimde devre dışı kalıyor; sonuç veya hata
  tekrar arayüz iş parçacığına taşınıyor. Pencere, devam eden çağrının yarıda
  kesilmesiyle yerel oturumu bozmayacak şekilde kapanmayı bekliyor.
- UI regresyon testi eklendi; merkezi hesabın bağlı ve bağlı olmadığı açılış
  senaryoları arka plan dönüşüyle doğrulandı.
- Ayarlar ekranındaki merkezi platform sağlık/bağlantı sınaması da aynı ortak
  arka plan işçisiyle çalışıyor; ağ beklerken kullanıcı diğer yerel ayarlara
  erişimini kaybetmiyor.

## 8 Eylül 2026 — Cihaz aktivasyonu ve lisans sözleşmesi

- Platform oturum servisine bağlı cihaz aktivasyonu ve lisans okuma işlemi
  eklendi. Bu çağrılar yalnız mevcut yerel firma/kullanıcı ve doğrulanmış API
  adresiyle eşleşen oturumda çalışıyor.
- Aktivasyonda ham donanım, MAC adresi veya kullanıcı bilgisi gönderilmiyor;
  yerel rastgele kurulum kimliği API istemcisinin sözleşmesine göre aktarılıyor.
- Lisans bilgisi alınmadan modül yetkisi verilmemesi için servis metodu
  `PlatformLicense` döndürüyor; arayüzdeki tam lisans/entitlement sunumu
  sonraki küçük adımda bu sözleşmeye bağlanacak.
- Merkezi hesap penceresi artık cihaz aktivasyonunu ve lisans okumasını giriş/
  oturum yenileme akışında arka planda çalıştırıp planı ve geçerliliği gösteriyor.
  Lisans servisi geçici olarak erişilemiyorsa oturum bilgisi korunuyor ve yerel
  çalışma devam ediyor.
- Ana pencere lisans yetkilerini yerel rol yetkileriyle kesiştiren ortak
  `effective_entitlements` kararını kullanıyor. Merkezi lisans verilmediğinde
  mevcut yerel davranış korunuyor; geçerli lisans verildiğinde lisans dışı
  modüller menüye eklenmiyor.
- Doğrulanan lisans metadata'sı yalnız firma, kullanıcı ve API adresi eşleşirse
  açılışta kullanılıyor. Merkezi oturum kapatılırken önbellek temizleniyor;
  parola veya yenileme anahtarı bu dosyaya yazılmıyor.

## 8 Eylül 2026 — Yedek bütünlüğü

- Yerel ZIP yedeklerine sürüm, dosya boyutu ve SHA-256 manifesti ekleniyor.
  Yedek oluşturulduktan sonra manifest tekrar doğrulanmadan işlem başarılı
  sayılmıyor.
- Log klasörü yedek kapsamı dışında kalıyor ve arşiv içindeki mutlak/üst dizin
  yolları reddediliyor. Böylece bozulmuş veya yol taşması içeren ZIP dosyaları
  ileride geri yükleme için güvenilir kabul edilmiyor.
- Geri yükleme önce geçici klasöre çıkarılıp tekrar hash kontrolünden geçiriliyor;
  mevcut firma alanı ancak bu kontrolden sonra zaman damgalı geri dönüş klasörüne
  taşınıyor. Arayüz onay ister ve işlem sonunda uygulamanın yeniden başlatılmasını
  bildirir.

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

## 9 Eylül 2026 — MANİM karar günlüğü

- MANİM yönlendirme ve müşteri eşleştirme kararları artık işlem sonucu içinde
  yapılandırılmış denetim kayıtları olarak tutuluyor. Her kayıt; rota/sonuç,
  bölge, banka, kuruşuna yuvarlanmış tutar, kaynak dosya-satır ve kural kodunu
  içeriyor.
- Karar günlüğü ham dekont açıklaması, IBAN veya müşteri adını saklamıyor;
  böylece işlem geçmişi denetlenebilir kalırken gereksiz kişisel veri çoğaltılmıyor.
- `OperationHistory.add_decision` firma, uygulama örneği ve aktif işlem lease
  kontrollerini ortak olay günlüğü üzerinden koruyor. Tamamlanan işlem sonradan
  karar olayı alamıyor.
- Netsis/FOM şablonları, çıktı sözleşmeleri ve yönlendirme kuralları bu adımda
  değiştirilmedi. Pytest ortamındaki mevcut Windows geçici klasör izin sorunu
  nedeniyle bu turda derleme doğrulaması yapıldı; tam geçici-dizin testleri
  uygun izinli ortamda yeniden çalıştırılmalıdır.

## 9 Eylül 2026 — Karar günlüğünün kullanıcı görünümü

- Geçmiş İşlemler ekranına işlem başına yapılandırılmış karar sayısı eklendi.
- İşlem ayrıntılarında bölge/banka, sonuç, tutar ve kural kodu okunabilir bir
  karar özeti olarak gösteriliyor; kullanıcı artık bir işlemin neden incelemeye
  kaldığını veya hangi rotaya ayrıldığını olay listesini açmadan görebiliyor.
- Eski işlemlerde karar olayı bulunmuyorsa ekran bunu açıkça belirtiyor;
  geçmiş veriler geriye dönük değiştirilmedi.

## 9 Eylül 2026 — Karar günlüğü filtreleri

- Geçmiş İşlemler ekranında karar sonucu, bölge ve banka filtreleri eklendi.
  Arama alanı modül, kullanıcı ve uygulanan kural üzerinden çalışıyor.
- Ekran, seçili son 100 işlemdeki kararların havale, inceleme, ödeme onaylandı,
  referanslı ve aynı banka virmanı dağılımını özetliyor.
- Filtreler yalnız yerel firma kapsamındaki işlem geçmişi üzerinde çalışır;
  merkezi sisteme Excel, banka veya müşteri verisi göndermez.

## 9 Eylül 2026 — FOM şablon ön kontrolü

- FOM Rapor Düzenleme ekranı seçilen satış veya tahsilat raporunun gerektirdiği
  özgün şablonu dosya seçilir seçilmez doğruluyor.
- Şablon uyuşmazsa işlem düğmesi pasif kalıyor ve kullanıcı raporlar okunmadan
  önce Ayarlar > Onaylı Şablon Kontrolü yönlendirmesini görüyor. Böylece geç
  aşamada hata alıp günlük iş akışının kesilmesi önleniyor.
- Bu kontrol şablonu değiştirmez, yeni kontrol değeri üretmez ve yalnız seçilen
  FOM çıktısının şablonunu etkiler. MANİM şablonları kendi doğrulamalarından
  geçmeye devam eder.

## 9 Eylül 2026 — Manuel ve birleşik kararların denetimi

- Eşleştirme ekranındaki havale, kısmi havale, ödeme onaylandı, referanslı,
  aynı banka virmanı ve incelemede bırakma kararları artık ilk otomatik öneriden
  ayrı birer `MANUAL` kararı olarak işlem geçmişine yazılıyor.
- Aynı müşteriye ait birden fazla banka hareketinin kuruşu kuruşuna otomatik
  birleşmesi veya tutar farkıyla incelemeye kalması, hareketlerin her biri için
  ayrı kaynak dosya/satır izi ve açık kural koduyla kaydediliyor.
- Reddedilen manuel kararlar da kaybolmuyor: negatif ödeme onayı, eksik BM kodu,
  hatalı toplam ve eksik manuel seçim `REVIEW` sonucu olarak görülebiliyor.
- Karar kayıtlarında müşteri adı, IBAN ve ham dekont açıklaması tutulmuyor;
  bu geliştirme Netsis/FOM şablonlarını veya çıktı üretim biçimini değiştirmiyor.

## 9 Eylül 2026 — Firma kapsamlı işlem sahipliği

- Çalışan bir işlem artık yalnız aynı firma, aynı kullanıcı ve işlemi başlatan
  uygulama örneği tarafından tamamlanabilir, başarısız sayılabilir veya yeni
  karar/olay kaydı alabilir.
- Kimliği olmayan eski bir istemci, firma kapsamlı işlem geçmişini göremez,
  değiştiremez ya da süresi geçmiş firma işlemini kesintiye uğramış sayamaz.
  Bu istemciler yalnız firma kimliği bulunmayan eski kayıtlarla sınırlıdır.
- Aynı uygulama örneği kimliği yanlışlıkla tekrar kullanılsa bile başka bir
  kullanıcı açık işlemi devralamaz. İşlem durumu geçişi firma, kullanıcı,
  sahiplik kimliği ve çalışan durum koşullarını birlikte doğrular.
- Bu adım yerel SQLite işlem geçmişini güçlendirir; merkezi PostgreSQL/RLS
  altyapısına geçişte aynı sahiplik sözleşmesi API katmanında da korunacaktır.

## 9 Eylül 2026 — Merkezi ağ sonucu teslimi

- Merkezi hesap ve bağlantı sınaması zaten arka plan işçisinde çalışıyordu;
  sonuç teslimi de artık açıkça arayüz iş parçacığına bağlı Qt slotlarıyla
  yapılıyor. Ağ işçisi hiçbir koşulda doğrudan düğme, uyarı veya durum metni
  değiştiremez.
- İşçi görevi sürerken düğmeler devre dışı kalır; sonuç tamamlandığında arayüz
  güvenle güncellenir ve iş parçacığı kapatılır. Bu düzen yavaş bağlantı,
  zaman aşımı ve pencere kapanışındaki nadir yarış koşullarını azaltır.
- Regresyon testi, arka plandaki merkezi oturum sonucunun gerçekten ana arayüz
  iş parçacığında işlendiğini doğrular. Finansal Excel/banka verisi merkezi
  platforma gönderilmez ve şablonlara dokunulmaz.

## 9 Eylül 2026 — Çıktı bütünlüğü kanıtı

- Tamamlanan her işlem, üretilen her yerel çıktı dosyası için SHA-256 özeti ve
  bayt boyutunu işlem geçmişine kaydeder. Dosya sonradan değiştirilir, silinir
  veya okunamaz hale gelirse Geçmiş İşlemler ayrıntısında açıkça belirtilir.
- İlk kayıt anında dosya oluşmamışsa ya da güvenli olmayan bir yol kullanılmışsa
  işlem özeti `KONTROL GEREKLİ` gösterir; bütünlük doğrulanmış gibi görünmez.
- Önceki sürümlerdeki işlemler değiştirilmez. Bunlar ayrıntı ekranında
  “bütünlük kaydı yok” olarak anlaşılır biçimde ayrılır.
- Parmak izi yerel işlem geçmişinde kalır. Excel hücre içeriği, müşteri, banka
  veya tahsilat verisi merkezi API'ye aktarılmaz; Netsis ve FOM şablonlarına
  müdahale edilmez.

## 9 Eylül 2026 — Kalıcı finansal hareket defteri

- Başarıyla tamamlanan MANİM işlemlerinin kararları, işlem tamamlanmasıyla aynı
  yerel veritabanı işlemi içinde ayrı bir finansal hareket defterine yazılır.
  Böylece çıktı oluşmadığı veya işlem tamamlanmadığı durumda yarım bir hareket
  kaydı bırakılmaz.
- Defter yalnız karar türü, sonuç, bölge, banka, tutar, kural kodu ve kaynak
  dosyanın adı/satırını taşır. Müşteri adı, müşteri kodu, IBAN, ham dekont
  açıklaması ve kullanıcının klasör yolu bu kayda alınmaz.
- Geçmiş İşlemler ayrıntısında kayıtlar sonuç-bölge-banka bazında gruplanarak
  toplam tutar ve hareket sayısıyla görünür. Böylece işlem sonrası hangi tutarın
  hangi rotaya gittiği, kaynak karar günlüğüne dokunmadan izlenebilir.
- Defter sorguları firma kapsamına bağlıdır; başka firmanın işlemine ait özet
  hareketler yerel geçmiş ekranından dahi okunamaz. Netsis/FOM şablonları ve
  çıktı yazım biçimleri bu adımda değiştirilmedi.

## 9 Eylül 2026 — Gerçek ERP aktarım kabul kaydı

- Çıktı dosyasının teknik olarak üretilmesi, ERP'nin onu kabul ettiği anlamına
  gelmez. Geçmiş İşlemler ekranında MANİM çıktısı için Netsis, FOM çıktısı için
  Psoft aktarım sonucu kullanıcı tarafından ayrıca “kabul edildi” veya
  “reddedildi” olarak kaydedilebilir.
- Bu sonuç Excel'e, şablona veya aktarımın kendisine müdahale etmez. Yalnız
  firma-kullanıcı kapsamındaki işlem günlüğüne zaman damgalı denetim olayı
  ekler; serbest hata metni alınmadığı için müşteri veya finansal bilgi çoğalmaz.
- Son kaydedilen sonuç detay ekranında geçerli kabul durumu olarak görünür;
  önceki kabul/ret sonuçları silinmeden olay günlüğünde tutulur. Böylece gerçek
  Netsis/Psoft denemeleri için ilerideki kabul test matrisi izlenebilir hale gelir.
- Son sonucu “reddedildi” olan işlem, teknik olarak dosya üretmiş olsa bile
  Operasyon Merkezi'nin dikkat listesine girer. Böylece günlük ekranda gerçek
  ERP aktarım sorunu, salt dosya oluşturma başarısından ayrı takip edilir.
- Sonuç kaydetme izni ayrı tanımlıdır: yönetici, operatör ve onaylayıcı bu
  kaydı oluşturabilir; salt okuma/denetçi rolü geçmişi inceleyebilir fakat dış
  aktarım sonucunu değiştiremez.

## 9 Eylül 2026 — Public otomatik kalite kontrolü

- GitHub Actions hata günlüğü incelendi ve üç gerçek regresyon düzeltildi:
  yedek bütünlük hatası artık açık bir “bozulmuş” bildirimi verir, Linux kalite
  kontrolünde merkezi oturum hiçbir zaman şifresiz saklanmadan Ayarlar ekranı
  güvenle oluşturulur, FOM'da değişmiş şablon çıktı klasörü yaratılmadan önce
  engellenir.
- Public test koşucusundaki sentetik şablon manifesti, üretimdekiyle aynı
  bütünlük kapısını kullanır. Public kaynakta gerçek yerel şablon veya müşteri
  verisi bulunmaz; onaylı Netsis/FOM şablonlarına dokunulmadı.

## 11 Eylül 2026 — Yerel haftalık operasyon özeti

- Operasyon Merkezi'nde son yedi güne ait işlem, başarı, manuel ERP kabulü,
  dikkat gerektiren işlem ve mutabakat kontrol adetleri ayrı bir özet kartında
  görünür hale getirildi.
- Özet yalnız yerel işlem geçmişinden türetilir; finansal satır, müşteri, IBAN
  ve Excel içeriği merkezi platforma taşınmaz.
- Tarih aralığı sabitlenmiş testlerle doğrulandı. Onaylı Excel şablonlarına ve
  çıktı yazımına bu adımda dokunulmadı.

## 11 Eylül 2026 — Geçmiş İşlemler dönem ve ERP eğilim görünümü

- Geçmiş İşlemler ekranına tüm zamanlar, son 7 gün, son 30 gün ve son 90 gün
  tarih filtreleri eklendi. Seçili dönem için başarılı/kısmi/hatalı işlem ile
  Netsis/Psoft kabul-ret adetleri aynı ekranda özetlenir.
- Bu görünüm işlem geçmişindeki durum ve kullanıcı kaydıyla sınırlıdır; finansal
  içerik, müşteri bilgisi veya Excel verisi merkezileştirilmez.
- ERP kabul kalitesi 2A paketi bu adımla tamamlandı. Onaylı çıktı şablonları,
  dosya adları ve manuel aktarım yöntemi değiştirilmedi.

## 11 Eylül 2026 — Ana iş ekranları için ortak iş akışı

- MANİM Aktarma, FOM Rapor Düzenleme ve Banka Mutabakatı ekranlarına ortak
  dört adımlı iş akışı göstergesi eklendi. Kullanıcı hangi aşamada olduğunu,
  neyin hazır olduğunu ve nerede kontrol gerektiğini tek bakışta görür.
- Gösterge yalnız arayüzde işlem durumunu açıklar; hiçbir Excel şablonunu,
  çıktı adını veya aktarım kararını değiştirmez.
# 12 Eylül 2026 — 2B yerel ekip görevleri ve onay

Operasyon Merkezi'nin üstüne görev panosu eklendi. Atayan/sorumlu ayrımı,
canlı üyelik ve rol kontrolü, görev bölgesi kapsamı, inceleme ve onaya gönderme,
gerekçeli onay/iade, hedef süre, geciken görevler, sürüm çakışması ve atomik
denetim kaydı birlikte uygulandı. Identity migration 2 eski üyelikleri korur.
101 ilgili test geçti; iki ekran genişliğinde görsel kontrol yapıldı.
Ayrıntılı kapsam ve yerel/merkezi kullanım sınırı: [2B](EKIP_GOREV_ONAY_2B.md).

## 12 Eylül 2026 — Netsis retlerinden güvenli yeniden çalışma

- Operasyon Merkezi, son sonucu reddedilmiş MANİM/Netsis işlemlerini ayrı bir
  çalışma alanında çıktı adı, işlem numarası, ana ret nedeni ve kaynakların
  hazır/eksik durumuyla gösterir.
- Yetkili kullanıcı normal banka-bölge çıktısını veya toplu banka kodlu çıktıyı
  seçip aynı kaynakları MANİM ekranına geri yükleyebilir. Bu işlem yalnız girdi
  ve profil seçimini hazırlar; simülasyonu, Excel üretimini veya Netsis
  aktarımını kendiliğinden başlatmaz.
- Silinmiş veya taşınmış kaynaklar açıkça listelenir ve yeniden çalışma düğmesi
  devre dışı kalır. Mevcut çıktılar silinmez; çıktı klasörü ayrıca açılabilir.
- Onaylı Netsis/FOM şablonları, şablon kontrol değerleri ve çıktı yazıcıları bu
  adımda değiştirilmedi. MANİM, geçmiş, rol/yetki ve tekrar-işleme kapsamındaki
  71 regresyon testi başarıyla geçti.

## 12 Eylül 2026 — 2D işlem sonrası operasyon kontrolü

- Yeni tamamlanan MANİM işlemlerinin gerçek bölge/banka dağılımı, kaynak
  gelen-giden tutarı, hazırlanan Netsis havalesi ve bekleyen bakiye Operasyon
  Merkezi'nde kalıcı olarak görüntülenir.
- Kısmi eşleştirmede tüm kaynak tutarı değil, gerçekten çıktı satırlarına
  yazılan tutar korunur. Gerçek Netsis kabul/ret sonucu bu teknik çıktı
  özetinden ayrı gösterilir.
- Büyük işlemlerde hareket satırları ikinci kez JSON içine kopyalanmaz; özet
  tutarlar küçük kalır, ayrıntılar mevcut firma kapsamlı hareket defterinden
  gerektiğinde yüklenir.
- Eski işlemlerde bu yeni sonuç kanıtı yoksa sistem tahmin üretmez. Onaylı
  Excel şablonları değiştirilmedi; ilgili 65 regresyon testi geçti.

## 12 Eylül 2026 — 2E operasyon kapanışı

- Yetkili kullanıcı, tamamlanmış MANİM operasyonunu seçip Netsis kabulünü veya
  seçilmiş ana ret nedenini doğrudan Operasyon Merkezi'nden kaydedebilir.
- Kayıt yalnız yerel denetim geçmişine yazılır. Netsis bağlantısı, otomatik ERP
  aktarımı, Excel hücresi veya onaylı şablon değişikliği yapılmaz.
- Ret sonucu aynı ekrandaki güvenli yeniden çalışma listesine yansır; kaynaklar
  mevcutsa kullanıcı yeni çalışma için MANİM ekranına geçebilir.
- Yetki, işlem geçmişi, ret yönlendirmesi ve entegrasyon durumu kapsamındaki
  27 test başarıyla geçti.

## 12 Eylül 2026 — Merkezi denetim zinciri doğrulaması

- Merkezi firma ve platform sahibi denetim zincirlerini değiştirmeden yeniden
  hesaplayan `platform_api/scripts/verify_audit_chain.py` eklendi.
- Denetim; firma kimliği, olay türü, sonuç, zaman ve öncül özet sözleşmesini
  kontrol eder. Bozuk olayda yalnız zincir adı ve olay numarasını bildirir;
  müşteri, banka, IBAN, Excel ya da finansal tutar okumaz, yazmaz veya ekrana
  çıkarmaz.
- Bu araç VPS'e ilk dağıtımdan ve her merkezi veritabanı yedeğinden sonra
  çalıştırılmak üzere hazırdır. Merkezi API henüz VPS'e kurulmadığı için günlük
  yerel Excel/Netsis akışına bağımlılık getirmez.

## 12 Eylül 2026 — Entegrasyon sonuç güvenilirliği

- Entegrasyonlar ekranı artık yalnız son 100 işlem yerine firma kapsamındaki
  tüm hafif işlem özetlerinden gerçek en güncel Netsis/Psoft sonucunu seçer.
- Sonucun tarihi de görünür. Geçmiş liste sırası farklı gelse bile en yeni işlem
  zamanı ve işlem numarası esas alınır; eski bir ret veya kabul yanlışlıkla
  güncel durum olarak gösterilmez.
- Bu iyileştirme canlı ERP/banka bağlantısı kurmaz; Excel, banka, müşteri ve
  finansal içerik yerelde kalır.

## 12 Eylül 2026 — 3A-2 ERP kabul matrisi

- Normal havale, toplu havale, hesaplar arası virman, FOM satış ve FOM
  tahsilat çıktıları tek kabul matrisi altında toplandı.
- Dosya/sayfa/başlık/satır/toplam kontrollerine; profil sabitleri, gerçek tarih
  türü, iki ondalıklı tutar biçimi, metin kimlik alanları ve şablona bağlı
  kritik hücre biçimleri eklendi.
- FOM satışın ilk 16 metin alanı ve tahsilatın kimlik/metin alanları
  sayıya dönüşmeden korunur. Profilde açıkça `text` olan masraf alanları
  yalnız adında `Tutar` geçtiği için para biçimine zorlanmaz.
- Beş çıktı türü Microsoft Excel ve onaylı yerel şablonlarla gerçek
  dosya oluşturma testinden geçti. Hiçbir onaylı şablon veya kontrol değeri
  değiştirilmedi.

## 12 Eylül 2026 — 3A-3 dosya bazlı ERP kabul kanıtı

- Netsis/Psoft kabul ve ret sonucu, işlemdeki belirli ERP çıktı dosyasına ve
  işlem tamamlanırken alınan SHA-256 parmak izine bağlandı.
- Değişmiş, taşınmış, silinmiş veya işleme ait olmayan dosyaya kabul kaydı
  yazılması engellendi. Birden fazla çıktının yalnız birine verilen kabul,
  tüm işlem kabulü olarak gösterilmiyor.
- Operasyon Merkezi, Geçmiş İşlemler, dönem eğilimi ve Entegrasyonlar ekranı
  aynı ortak toplulaştırma kuralına geçirildi. Eski işlem düzeyi kayıtlar
  geriye uyumlu kaldı.
- Hedef kapsamda 35 test, ardından tam regresyon paketi başarıyla geçti.
  Onaylı şablonlara ve şablon kontrol değerlerine dokunulmadı.

## 12 Eylül 2026 — 3A-4 ERP ret eğilimi

- Geçmiş İşlemler ekranı, seçili dönem için Netsis ve Psoft tarafındaki en sık
  iki güvenli ret kategorisini kabul/ret özetine ekler.
- Dosya bazlı son karar esas alınır: daha sonra kabul edilen çıktı, eski ret
  kategorisinde sayılmaz. Bu yalnız karar desteğidir; otomatik düzeltme veya
  otomatik ERP kabulü yapmaz.
- Hedef işlem geçmişi, eğilim ve arayüz testlerinde 28 test geçti. Onaylı
  şablonlara, dosya adlarına veya hücre biçimlerine dokunulmadı.

## 12 Eylül 2026 — 3B ERP kalite sinyalinin operasyon yönetimine bağlanması

- Operasyon Merkezi'ne son yedi günlük Netsis/Psoft kabul-ret sayıları ve en
  sık iki güvenli ret kategorisini gösteren ERP kalite sinyali eklendi.
- Kısmi dosya sonuçları tam kabul gibi gösterilmez. Sinyal yalnız kullanıcıyı
  kontrol için yönlendirir; otomatik düzeltme, ERP aktarımı veya şablon
  değişikliği yapmaz.
- Operasyon merkezi, eğilim, güvenli yeniden çalışma ve arayüz kapsamındaki
  17 test geçti. Onaylı şablonlar korunuyor.
