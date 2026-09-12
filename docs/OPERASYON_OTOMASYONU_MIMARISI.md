# Operasyon otomasyonu — karar ve uygulama planı

Karar tarihi: 10 Eylül 2026. Kapsam: mimari yol haritasının 1. aşaması.
Bu belge bu aşamanın iş sırasıdır; tamamlanan ve bekleyen işler aşağıda ayrıdır.

## Amaç

Bir aktarımın hangi ayarla hesaplandığı bilinsin; belirsiz kayıtlar uygulama
kapanınca kaybolmasın; yetkili kişi sorumluluğu alıp düzeltebilsin; sonuçlar
dosya üretmeden önce görülebilsin. Kullanıcı tarafından doğrulanan finansal
kurallar ve onaylı Netsis/Psoft şablon sözleşmeleri bu işin temelidir.

## Mevcut koddan doğrulanan durum

- `OperationHistory` firma/kullanıcı/süreli işlem sahipliğini, karar günlüğünü,
  finansal hareket özetini, çıktı bütünlüğünü ve dış ERP kabul sonucunu tutuyor.
- `OperationCenter` geçmişteki kısmi/başarısız işlemleri gösteriyor. Bu ekranın
  bulunması, kalıcı ve atanabilir bir inceleme kuyruğunun hazır olduğu anlamına gelmiyor.
- `MovementRouter`, `CombinedBankMovementMatcher`, `ManualResolutionService`
  ve `ManimOutputService` ayrı sorumluluklar olarak mevcut. Yeni otomasyon bu
  servislerin kararlarını kullanacak; ikinci bir eşleştirme motoru kurulmayacak.
- Birleşik havalede tüm hareketlerin toplamı tahsilatla kuruşu kuruşuna
  eşitse otomatik aktarım var; fark varsa kullanıcı birleştirme/düzeltme yapıyor.
- Çıktı üretimi geçici klasörden yayınlanıyor. Müşteri listesi önbelleği halen
  hesaplamanın erken aşamasında güncelleniyor; gerçek salt okunur simülasyon
  için bu yan etkinin hesaplamadan ayrılması gerekiyor.
- Kaynak satırların kalıcı tahsilat tüketim kaydı henüz yok. Finansal özet
  günlüğü, bir tahsilatın tekrar kullanılmasını engelleyen kayıtla aynı şey değil.

## Ana kararlar

### Yerel işlem, firma kapsamlı saklama

Bu aşama mevcut firma çalışma alanındaki SQLite üzerinde yürür; VPS gerektirmez.
Merkezi PostgreSQL API'sine banka, müşteri, Excel veya tahsilat içeriği gönderilmez.
Gelecekte merkezi iş yönetimi gerekirse yalnız kimlik/durum gibi izin verilen
metadata için ayrı API sözleşmesi hazırlanır; masaüstü doğrudan PostgreSQL'e bağlanmaz.

### İşlemde kullanılan ayar sabittir

İşlem, kullanılacak bölge kodlarını ve çözümlenmiş girdi/çıktı/müşteri
profillerini başlarken yakalar. İşçi aynı kopyayı kullanır. Yeni ayar seçimi
sonraki işlemde geçerlidir. İçerik değişirse firma ve modül kapsamında yeni
sürüm doğar; eski ayara dönülürse o ayarın önceki sürümü yeniden kullanılır.

Sürüm numarası bir şablon onayı değildir. Şablonlar mevcut onaylı dosya ve
kontrol değeri denetiminden geçmeye devam eder. Geçmiş ayar kaydı, eski şablonu
geri yazmaya veya doğrulamayı atlamaya izin vermez.

İlk bölüm kullanılan ayarları kaydeder. Ayarı kimin düzenlediği, neden
değiştirdiği ve yayına aldığına ilişkin yönetim akışı sonraki bölümdedir.
Sürümdeki `created_by`, ayarı değiştiren kişi değil, o ayarla ilk işlemi açandır.

### Kaynak kimliği ve toplu inceleme

Kalıcı inceleme için kaynak kimliği dosya içeriğinin özeti + sayfa + satırdan
üretilir; yalnız dosya adı yeterli değildir. Birleştirilmiş inceleme kaydı,
gruptaki banka hareketlerinin tümünü ayrı kaynak kimlikleriyle saklar.
Tek satırın tutarı grubun toplamı gibi kullanılamaz. Bölge, banka, gün ve
tahsilat havuzu sınırlarını mevcut birleşik eşleştirme servisi belirler.

Dosya değiştirilirse veya kaybolursa eski öneriyle sessizce devam edilmez;
kullanıcıdan doğru kaynak seçmesi istenir ve yeni değerlendirme yapılır.
Parasal yeni kalıcı sözleşme tam sayı kuruş/Decimal kullanır. Mevcut float
tabanlı motorun tümünü aynı değişiklikte dönüştürmek ayrı bir regresyon riski
olacağından dönüşüm sınırları açıkça test edilir.

### Kalıcı karar ile aktarım ayrı olaylardır

Kuyruk durumları: `OPEN`, `ASSIGNED`, `RESOLVED`, `CANCELLED`.
Atama, mali onay yerine geçmez. Kararı veren kullanıcı, revizyon ve eski/yeni
durum kaydedilir. Aynı kayıt iki kullanıcı tarafından açılırsa sürüm kontrolü
ikinci kaydın ilk kararı ezmesini engeller. İzinler `AuthenticatedSession.can()`
üzerinden uygulanır; UI içinde rol adı karşılaştırması yapılmaz.

Manuel karar, kısmi tutar ve birleşik karar mevcut mali doğrulama servisinden
geçer. Fazla gelen paranın bekleyen kısmı ayrı kalır. Kullanıcının onayladığı
pasif cari kodu akışı ve negatif Ödeme Onaylandı denetimi korunur.

### Önce hesapla, sonra yayınla

Simülasyon aynı girdi + aynı ayar sürümü + aynı eşleştirme hafızası görünümü
ile gerçek işlemin karar planını üretir. Çıktı yazmaz, müşteri önbelleğini,
eşleştirme hafızasını veya işlenmiş dosya geçmişini güncellemez, çözülmüş kayıt
ya da tüketilmiş tahsilat oluşturmaz. Farklı bir motor kullanılmaz.

Gerçek aktarım öncesi kaynaklar ve ayar sürümü tekrar karşılaştırılır.
Önizlemeden sonra kaynak/karar değişmişse yeniden değerlendirme gerekir.
Dosya sistemi yayını ile SQLite kaydı tek veritabanı işlemi değildir: yayın
manifesti ve kurtarma adımı tasarlanarak kesinti sonrası çift çıktı/çift
tahsilat riski yönetilir. Salt dosya özetiyle 'tam bir kez aktarım' iddiası yapılmaz.
Gerçek Netsis/Psoft kabulü mevcut kullanıcı kabul kaydıyla ayrı izlenir.

## Uygulama sırası ve tamamlanma ölçütleri

| Bölüm | İçerik | Bitiş ölçütü | Durum |
| --- | --- | --- | --- |
| 1A | MANİM işlem ayarını sabitleme ve geçmişe bağlama | Eşzamanlı başlatma, firma ayrımı, eski kayıt, canlı ayar değişimi ve geri alma testleri | Tamamlandı |
| 1B | Ayar değişikliklerinin sürüm/karar yönetimi | Yetkili değişiklik, önceki/yeni değer ve kullanıcı izi; çakışan düzenleme reddi; FOM'a uygun kapsam | Tamamlandı |
| 1C | Kalıcı inceleme ve kaynak kimlikleri | Yeniden açılışta tüm grup üyeleri/tutarlar korunur; atama/yetki/çakışma testleri geçer | Tamamlandı |
| 1D | Hesaplama ile kalıcı etkilerin ayrılması ve simülasyon | Önizleme hiçbir çıktı/önbellek/tüketim kaydı yazmaz; aynı şartlarda gerçek planla eşleşir | Tamamlandı |
| 1E | Kontrollü yeniden işleme ve kurtarma | Tahsilatın çift kullanımı ve kesinti sonrası tekrar yayın korunur; kalan bakiye izlenir | Tamamlandı |

Her bölüm tek uçtan uca geliştirme paketi olarak tamamlanır: servis, gerekli
veritabanı geçişi, UI, ilgili regresyonlar ve dokümantasyon beraber teslim edilir.
Küçük düğme değişiklikleri ayrı mimari aşama sayılmaz. Kritik veri/işlem sınırı
kararları Astra yüksek eforla; netleşen paketin uygulaması Sol yüksek eforla
yürütülebilir. Model değişimi test ve kabul şartlarını değiştirmez.

## 1E: yayın günlüğü, kontrollü tekrar ve tahsilat kullanım defteri

- Çıktı klasörü görünür olduktan sonra yerel durum kaydı tamamlanmadan kesinti
  olursa, kaynak özetleri `PUBLISHED` durumunda saklanır. Aynı kaynaklar sessiz
  biçimde tekrar işlenmez; kullanıcı Operasyon Merkezi'ndeki kurtarma alanında
  eski klasörü görür.
- Kullanıcı eski çıktının Netsis/Psoft'a aktarılmadığını kontrol ettikten sonra
  “Yeniden İşlem İçin Onayla” adımıyla tekrar çalıştırmaya izin verebilir.
  Bu adım eski klasörü silmez, ERP kabul sonucu varsaymaz ve onaylı şablonlara
  dokunmaz.
- Tahsilat satırı tüketim defteri kaynak dosya özeti + sayfa + satır kimliğiyle
  tutulur. Kısmi eşleşme yalnız kullanılan kuruşu düşer; kalan bakiye yeniden
  aday olabilir. Tam tüketilen kaynak satırı tekrar aday yapılamaz.
- Simülasyon defteri yazmaz. Gerçek aktarımda bakiye son kez doğrulanır ve
  aynı satırı eşzamanlı iki gerçek işlemin aşması reddedilir. Kullanıcı elle
  yeni cari/tutar girebilir; ancak kaynak kimliği olmayan satır için hayali
  tüketim kaydı üretilemez.

## 1A teknik sözleşmesi

- `execution_configuration.py`: değiştirilemez JSON kopyası ve içerik özeti;
  sürüm kaydı ve işlemle atomik bağlama.
- `manim_configuration.py`: mevcut profil depolarının gerçekten seçtiği
  profilleri ve yüklenmiş bölge ayarlarını yakalama/çözümleme. Algoritma değişirse
  `MANIM_RULESET_VERSION` artırılır. Bu sürüm eski motoru yeniden çalıştırma sağlamaz.
- `OperationHistory.start(configuration=...)`: işlem, ayar sürümü ve olay aynı
  SQLite işleminde yazılır. Başarısız bağlamada yarım işlem kaydı oluşmaz.
- `operation_schema_migrations` sürüm 1: `operation_configuration_versions`
  ve `operation_configurations` tabloları. Kimlik veritabanının migrasyonları ayrıdır.
- `scope_key + module_id + fingerprint` aynı ayarın çoğalmasını önler;
  `scope_key + module_id + revision` sürüm numarasını tekilleştirir.
- `OperationHistory.configuration(id)` yalnız mevcut firma geçmişinden okur
  ve içerik özetini doğrular. Sürümler uygulama API'sinde güncellenmez/silinmez.
  SHA-256 bozulma tespitidir; tüm yerel veritabanını değiştirebilen saldırgana
  karşı imza veya bağımsız değiştirilemez kayıt olduğu iddia edilmez.
- Olay günlüğü yalnız sürüm numarası/özeti taşır. Ayrıntılı ayarlar sadece
  yerel veritabanında kalır; kaynak Excel veya müşteri eşleştirme hafızası bu
  ayar kaydına eklenmez. Yeni şablon kontrol değeri üretilmez.
- Eski işlemlere geriye dönük hayali sürüm atanmaz. MANİM dışındaki modüller
  bu bölümde zorunlu ayar kaydına geçirilmedi.

## Bu bölümün doğrulaması

13 yeni test dahil toplam 103 ilgili test geçti. Ayar kopyasının dışarıdan
değiştirilememesi, sürüm yeniden kullanımı, şirketler arası erişim, eski şema
geçişi, hatada atomik geri alma, sekiz eşzamanlı işlem ve işlem devam ederken
profil/bölge dosyasının değişmesi doğrulandı. Birleşik havale, bölge ayrımı,
toplu çıktı ve şablon koruma regresyonları geçti.

Testler sentetik verilerle yapıldı; gerçek Netsis/Psoft aktarımı yapılmadı.
Windows test klasörü erişim kısıtı nedeniyle testler normal kullanıcı
izinleriyle yeniden çalıştırıldı. Onaylı kaynak Excel şablonlarına dokunulmadı.

## 1B teknik sözleşmesi

- `configuration_change_audit.py`, düzenlenebilir bölge/profil ayarları için
  firma kapsamlı yerel denetim kaydı tutar. Konu başına sürüm, yapan kullanıcı,
  tarih, önceki/yeni değer ve içerik özeti saklanır.
- Ayarlar menüsü yalnız `settings.manage` yetkisiyle açıldığından bu kaydı
  oluşturacak ekran da aynı merkezi yetki kararıyla sınırlandırılmıştır.
  Arayüz rol adına göre karar vermez.
- Aktif girdi/çıktı/müşteri listesi profili değişimleri ile bölge ayarları
  kaydedilir. Kullanıcının yazdığı profil içeriği de yerel değişiklik kaydı
  olur. FOM bu üç MANİM profiliyle çalışmadığı için FOM'un onaylı satış/tahsilat
  şablonuna yeni düzenleme yetkisi veya kayıt yolu eklenmemiştir.
- Değişiklik geçmişi Ayarlar ekranından okunabilir. Şablonları geri yüklemez,
  Excel'e veri yazmaz ve merkezi API'ye içerik göndermez.
- Aynı konu için ikinci ayar penceresi, ilk pencerenin kaydından önceki durumu
  kullanırsa değişiklik geçmişi yazmayı reddeder. Kullanıcı ekranı yeniler ve
  güncel ayara göre tekrar karar verir. Bu koruma uygulamanın izlediği ayar
  değişiklikleri arasındadır; uygulama dışından JSON dosyasını elle değiştirmek
  desteklenen bir ayar yöntemi değildir.

Bu bölüm için 7 yeni denetim kaydı testi eklendi. Sıradaki 1C kalıcı inceleme
kuyruğudur; bu kuyruk tüm birleşik banka hareketlerinin kaynaklarını ve toplamını
tek kayıt altında koruyacaktır.

## 1C ilk teslim sözleşmesi

- İnceleme kuyruğu yerel `operations.sqlite3` içinde firma kapsamıyla tutulur;
  uygulama yeniden açıldığında açık, atanmış ve çözülmüş kayıtlar yeniden
  listelenebilir.
- Yeni kuyruk üyeleri kaynak dosyanın SHA-256 özeti, veri sayfası ve satır
  numarasıyla kimliklenir. Operasyon Merkezi'ndeki “Kaynakları Doğrula” adımı
  yalnız dosya özetini kontrol eder; kaynak değişmişse eski kararın otomatik
  uygulanmasına izin vermez.
- Kuyruk grupları sürümlüdür. Atama, çözme ve yeniden açma işlemleri önceki
  sürümü doğrular ve geçişi ayrı denetim olayı olarak saklar; eski açık ekranın
  yeni bir kararı ezmesi engellenir.
- Her grup kaynak dosya/satır, bölge, banka, tutar ve kısa neden alanlarını
  korur. Müşteri adı, cari kodu, IBAN ve ham açıklama kuyruğa yazılmaz.
- Atama, çözme ve yeniden açma durum geçişleri yalnız aynı firma kaydında ve
  geçerli durumdan yapılabilir. Sonuç kodu boş veya serbest uzun metin olamaz.
- MANİM çıktısı üretildikten sonra inceleme satırları kuyruğa yazılır; mevcut
  inceleme Excel'i ve onaylı Netsis/FOM şablonları aynen korunur.
- Birleşik hareketlerde ekranda tek karar gösterilse bile inceleme Excel'i ve
  kuyrukta grubun bütün banka hareketleri alt üye olarak korunur. Böylece iki
  veya üç havalenin yalnızca ilk satırının kaybolması engellenir.
- Kuyruk kayıtlarının Ayarlar dışındaki operasyon ekranında atanıp kapatılması
  ve grup bazlı yeniden açılması 1C'nin sonraki alt adımıdır.

Operasyon Merkezi artık kuyruktaki grupları da görsel olarak listeler: durum,
bölge, banka, alt hareket sayısı, toplam tutar ve kısa neden aynı satırda
izlenir. Yetkili kullanıcı seçili grubu üzerine alabilir, kısa bir karar koduyla
çözebilir veya çözülmüş grubu yeniden açabilir; her işlem firma kapsamı ve
geçerli durum geçişiyle kontrol edilir.

## 1D eşleşme kanıtı

- Önizleme, seçili dosyalar için yakalanmış MANİM profil/bölge ayarının özetini
  aynı açık ekran oturumunda tutar.
- Aktarım başlarken ayar özeti değişmişse kullanıcı günlükte açık uyarı görür.
  İşlem sonunda MANİM ve Netsis toplamları önizlemeyle tekrar karşılaştırılır.
- Aynıysa günlük “simülasyon doğrulandı” kaydı alır; farklıysa iki Netsis
  toplamı birlikte yazılır. Bu karşılaştırma yalnız görünürlük sağlar; otomatik
  aktarım kararı veya şablon değişikliği üretmez.
- Sağ çalışma alanında simülasyon, işlem günlüğünden ayrılmış bir aktarım planı
  olarak gösterilir: gelen/giden kaynak tutarı, Netsis havale toplamı, bekleyen
  bakiye ve bölge/banka dağılımı ayrı görünür. Ödeme onaylandı, referanslı ve
  virman rotaları Netsis havalesiyle karıştırılmaz; yalnızca gerçekten
  açıklanamayan farklar kontrol uyarısı üretir.
- İşlem günlükleri ortak bir etkileşimli görünüm kullanır. Kullanıcı kayıtları
  seviye ve metinle filtreleyebilir, seçili teknik ayrıntıyı açabilir ve tüm
  günlüğü panoya kopyalayabilir. Bu katman karar üretmez ve onaylı Excel
  şablonlarına dokunmaz.

## 1E ekip atama ve inceleme sorumluluğu

- İnceleme kuyruğu firma kapsamını korur; atama işlemi yalnız açık veya atanmış
  gruplarda, sürüm denetimiyle yapılır. Aynı kayıt iki açık ekrandan güncellenirse
  eski ekran kararı ezemez.
- Yönetici ve operatör, aktif firma kullanıcılarına iş atayabilir. Onay
  sorumlusu yalnız seçili işi kendi üzerine alabilir, çözebilir veya yeniden
  açabilir. Denetçi kuyruk bilgilerini salt okunur izler.
- Operasyon Merkezi; atanan kişinin görünen adını, grup durumunu, bölge/banka
  özetini, hareket sayısını ve toplamını birlikte gösterir. Atama listesinde
  yalnız aktif ve aynı firmaya bağlı ekip üyeleri görünür.
- Kullanıcıya atama, Excel içeriğine veya eşleştirme kararına müdahale etmez;
  yalnız yerel kuyrukta sorumluluk ve denetim olayı oluşturur. Müşteri adı,
  cari kodu, IBAN ve ham dekont açıklaması bu görünümde tutulmaz.
- Doğrulama: kimlik, rol, kalıcı kuyruk, operasyon merkezi ve işlem geçmişi
  kapsamında 32 test başarıyla geçti.

## 1F ana operasyon ekranları için iş akışı deneyimi

- MANİM Aktarma, FOM Rapor Düzenleme ve Banka Mutabakatı ortak bir dört adımlı
  çalışma yüzeyi kullanır: girdi seçimi, doğrulama/plan, işlem veya kontrol ve
  sonuç raporu/çıktısı.
- Adımlar bekliyor, aktif, tamamlandı ve dikkat gerekli durumlarını arayüzde
  açıkça gösterir. Bu görünüm karar vermez; yalnız mevcut işlem sonucunu
  anlaşılır hâle getirir.
- MANİM'de simülasyon tamamlandığında plan aşaması; FOM'da tanınan rapor ve
  onaylı şablon kontrolü; Banka Mutabakatı'nda ekstre-Netsis çiftinin hazır
  oluşu kullanıcıya doğrudan görünür. Hata veya inceleme gerektiren sonuçlar
  turuncu dikkat durumu ile ayrılır.
- Ortak bileşen yalnız PySide arayüz kodudur. Excel şablonlarına, dosya
  adlarına, eşleştirme algoritmasına ve manuel Netsis/Psoft aktarım akışına
  müdahale etmez.
- Doğrulama: ekran iş akışı, FOM motoru, banka mutabakatı ve operasyon merkezi
  kapsamındaki 28 test başarıyla geçti.
