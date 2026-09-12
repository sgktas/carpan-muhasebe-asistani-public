# ERP kabul kalitesi — 2A planı

Karar tarihi: 11 Eylül 2026. Bu belge, operasyon otomasyonu 1A–1E
tamamlandıktan sonraki ERP kabul güvenliği iş sırasını tanımlar.

## Amaç

Bir dosyanın oluşturulması, Netsis veya Psoft'un o dosyayı kabul ettiği anlamına
gelmez. 2A; kullanıcı ERP'ye geçmeden önce yakalanabilen yapısal hataları açık
bir neden ve konumla durdurur, gerçek ERP sonucu ise kullanıcının kabul/ret
kaydı olarak ayrı izlenmeye devam eder.

Onaylı kaynak şablonlar bu aşamada yalnız okunur doğrulanır. Şablon yeniden
oluşturulmaz, adı/sayfası/sütunu değiştirilmez ve kontrol değeri otomatik
güncellenmez.

## 2A-1 — MANİM aktarım ön kontrolü

- Excel yazımı başlamadan önce her Netsis havale satırının cari kodu, işlem
  tarihi ve pozitif tutarı doğrulanır.
- Banka hesap kodu isteyen profilde satırdaki BM kodu, aktif bölge ayarındaki
  aynı bölge/banka koduyla birebir uyuşmalıdır. Toplu dosyada her satır kendi
  bankasıyla kontrol edilir.
- Bölge bazlı dosyada farklı bankaya ait satır; toplu hesaplar arası virmanda
  farklı banka transferi, boş kaynak/hedef BM kodu, yanlış genel referans veya
  yanlış Plas.Kodu dosya oluşmadan reddedilir.
- Hata metni Netsis'in genel uyarısını taklit etmez; bölge, banka ve çıktı
  satırını açıkça verir. İnceleme kaydı/şablon/çıktı klasörü oluşturulmaz.
- Yazımdan sonra mevcut çıktı sözleşmesi ikinci kez sayfa, başlık, satır sayısı,
  tutar toplamı ve onaylı hücre biçimini doğrular.

## 2A-2 — FOM çıktılarının birlikte yayımlanması (tamamlandı)

- Müşteri, satış ve tahsilat çıktıları aynı disk üzerindeki ayrı geçici
  çalışma klasöründe hazırlanır. Satış/tahsilat ERP sözleşmesi kontrolleri
  bu klasörde tamamlanır; tüm dosyalar mevcutsa sonuç klasörüne taşınır.
- Yazım, sözleşme veya taşıma hatasında yeni bir `FOM AKTARMA` sonuç klasörü
  yayımlanmaz. Normal hata dönüşünde geçici çalışma alanı temizlenir;
  önceki sonuç klasörleri ve kaynak şablonlar korunur.
- Dönen dosya yolları yayımlanan klasörü gösterir. Aynı günün eski çıktısı
  üzerine yazılmaz; mevcut numaralandırma ve özgün ERP dosya adları korunur.
- Ani süreç/elektrik kesintisinde geçici çalışma alanı kalabilir; bu alan
  tamamlanmış sonuç klasörü sayılmaz. ERP kabulü yine ayrı kullanıcı kaydıdır.
- Doğrulama: FOM ve çıktı sözleşmesi testlerinde 20 test geçti. Geç tahsilat
  yazım hatası, gerçek satır sayısı sözleşmesi hatası, taşıma hatası ve başarılı
  birlikte yayın sentetik verilerle sınandı; gerçek ERP aktarımı yapılmadı.

## 2A-4 — Banka mutabakatı farkının operasyon takibi (tamamlandı)

- Banka mutabakatı tamamlandığında işlem geçmişine yalnız bölge, durum,
  bankada/Netsis'te açık kayıt adetleri ve tutar farkları eklenir. Ayrıntılı
  açıklama ve satır içerikleri yerel nokta atışı düzeltme raporunda kalır.
- Operasyon Merkezi; dönem hareketleri tutup devreden bakiye farklıysa bunu,
  bakiye tutup açıklanamayan satırlar varsa açık kayıt adetlerini, genel fark
  varsa fark tutarını ayrı kontrol nedeni olarak gösterir.
- Bu alan dosya üretmez, ERP'ye bağlanmaz ve mutabakat sonucunu değiştirmez.
- Doğrulama: mutabakat motoru, rapor ve operasyon ekranı kapsamındaki 26 test
  geçti. Gerçek banka/Netsis dosyasıyla işlem yapılmadı.

## Sıradaki 2A alt teslimleri

1. Manuel ERP kabul/ret ve mutabakat farklarından yerel haftalık operasyon
   özeti üretmek; yalnız sayısal durumlar ve adetler kullanılacak.

## 2A-3 — Manuel ERP kabul sonucu ve ret nedeni (tamamlandı)

- Geçmiş İşlemler ekranında kullanıcı, manuel Netsis/Psoft aktarımının kabul
  edildiğini veya reddedildiğini kaydeder. Ret seçilirse banka hesap kodu,
  şablon/sütun yapısı, zorunlu alan, tutar/toplam, dosya biçimi veya aktarım
  ekranı seçeneklerinden biri seçilir.
- Serbest hata metni alınmaz; müşteri, banka hareketi veya Excel içeriği bu
  kayda eklenmez. Eski kayıtlardaki retler kategori olmadan okunmaya devam eder.
- Operasyon Merkezi son 100 işlemdeki Netsis ve Psoft ret adetlerini ayrı
  gösterir. Öncelikli takip satırı seçilen ret nedenini açıkça yazar.
- Bu kayıt ERP ile canlı bağlantı kurmaz; kullanıcının manuel aktarım sonucunu
  yerel işlem geçmişine ekler.

## 2A-5 — Yerel haftalık operasyon özeti (tamamlandı)

- Operasyon Merkezi, son yedi gündeki işlem sayısını, başarılı işlemleri,
  kullanıcının kaydettiği Netsis/Psoft kabul adetlerini, dikkat gerektiren
  işlemleri ve açık mutabakat kontrollerini ayrı gösterir.
- Özet yalnız yerel işlem geçmişindeki durum/adet bilgisinden oluşur; banka
  hareketi, müşteri, IBAN, Excel içeriği veya tutar merkezi API'ye gönderilmez.
- Tarihi bozuk veya dönem dışı eski kayıtlar özete dahil edilmez. Mevcut
  günlük takip kartları ve ayrıntılı inceleme listesi korunur.
- Doğrulama: operasyon merkezi, çalışma alanı ve işlem geçmişi kapsamındaki
  20 test başarıyla geçti.

## 2A-6 — Dönem filtresi ve kabul/ret eğilimi (tamamlandı)

- Geçmiş İşlemler ekranı; tüm zamanlar, son 7 gün, son 30 gün ve son 90 gün
  seçenekleriyle işlem kayıtlarını filtreler.
- Seçili görünüm için başarılı/kısmi/hatalı işlemler ile Netsis ve Psoft
  kabul-ret sayıları anlaşılır bir satırda gösterilir. Bu bilgi yalnız yerel
  işlem geçmişinden okunur ve herhangi bir dış servise gönderilmez.
- Tarihi bozuk eski kayıtlar dönemli listeden güvenle dışarıda kalır; “tüm
  zamanlar” görünümü eski kayıtları korur.
- Doğrulama: dönem filtresi, kabul-ret eğilimi, işlem geçmişi ve operasyon
  çalışma alanı kapsamında 22 test başarıyla geçti.

## 2A sonucu

ERP kabul kalitesi yerel iş akışı tamamlandı. Bir sonraki mimari pakette bu
verilerden yararlanarak ekip yetkileri, iş atama ve onay akışının operasyon
ekranındaki kullanılabilirliği güçlendirilecektir. Excel şablonları ve manuel
Netsis/Psoft aktarım yöntemi bu kapsamda değiştirilmez.

## 2B — Ekip görevleri ve onaylar

12 Eylül 2026: yerel inceleme görevleri için uygulandı. Atama, sahiplenme,
inceleme, onaya gönderme, onay/iade, hedef süre, görev bölgesi kapsamı,
karar geçmişi ve yetkili yeniden açma aynı servisle yönetilir.
Kapsam, rol matrisi ve doğrulama: [2B sözleşmesi](EKIP_GOREV_ONAY_2B.md).
Genel rapor satırlarına bölge yetkisi ve merkezi çok bilgisayarlı görev paylaşımı
bu yerel görev kapsamından ayrı işlerdir.

## 2C — Gerçek kullanım sağlamlaştırması

12 Eylül 2026: otomatik performans ve ekran ölçeği bölümü uygulandı.
Günlük satırları toplu yüklenir; uyarı/hata sayaçları geçmiş satırları her
eklemede yeniden taramaz. MANİM sonuç günlükleri ve kararları geçmişe
toplu veritabanı işlemleriyle yazılır; firma/kullanıcı/çalışan işlem sahibi
kontrolleri korunur. Geçersiz karar veya yazma hatası toplu kaydı geri alır.
Arka plan işinin sonuç işleyicisi bitmeden yeni iş başlatılamaz.

Doğrulama: 81 ilgili test geçti. Testler 20.000 günlük satırı, 5.000 geçmiş
olayı, 40 ardışık arka plan işi, veri eksiksizliği ve atomik geri alma içerir.
%125 ve %150 Qt ölçeğinde dört ek ekran test koşumu geçti; örnek görseller
incelendi. Bunlar gerçek çok saatli kullanım veya Netsis kabul testi değildir.

Kalan kabul: iş bilgisayarında gerçek günlük dosyalarla uçtan uca kullanıcı
denemesi ve uzun oturum gözlemi. Merkezi çok bilgisayarlı görev paylaşımı,
canlı dağıtım/yedekleme ve banka/ERP bağlantıları ayrı sonraki kapsamdır.

## 2D — İşlem sonrası operasyon kontrolü

12 Eylül 2026: yerel ilk teslim uygulandı. Tamamlanan yeni MANİM işlemlerinin
gerçek sonuç dağılımı, işlem geçmişine küçük ve sürümlü bir özet olarak yazılır.
Operasyon Merkezi'nde son 20 işlem arasından seçim yapılarak MANİM gelen/giden,
Netsis havale, bekleyen bakiye ve bölge/banka dağılımı görüntülenir. Netsis'in
gerçek kabul/ret sonucu ayrıca gösterilir; dosya üretimi ERP kabulü sayılmaz.

Kısmi havalede kaynak tutarı yerine gerçekten hazırlanan Netsis tutarı saklanır.
Binlerce kaynak satırı özet JSON içinde tekrar edilmez; ayrıntı gerektiğinde
firma kapsamlı finansal hareket defterinden yüklenir. Eski işlemler geriye dönük
uydurulmaz ve ayrıntılı sonuç özeti bulunmadığı açıkça belirtilir.

Bu ekran salt okunurdur; işlem kararını, tüketim defterini veya Excel çıktısını
değiştirmez. Onaylı şablonlar ve şablon kontrol değerleri bu aşamada
değiştirilmedi. Sonuç özeti ve ilgili MANİM/operasyon regresyonlarında 65 test
başarıyla geçti. Kalan kabul gerçek günlük dosyayla yeni bir işlem tamamlayıp
bölge/banka kartlarını kullanıcı gözüyle doğrulamaktır.

## 2E — Operasyon kapanışı ve ERP sonucu

12 Eylül 2026: yetkili kullanıcı tamamlanan MANİM işleminde Netsis sonucunu
Operasyon Merkezi'nden doğrudan kaydedebilir. Kabul veya ret işlemi, mevcut
Geçmiş İşlemler denetim kaydıyla aynı firma/kullanıcı/rol kurallarını kullanır.
Ret durumunda ana hata nedeni seçilir; kayıt, güvenli yeniden çalışma alanında
görünür. Bu düğme ERP'ye bağlanmaz, Excel'i değiştirmez veya otomatik kabul
kararı vermez.

Bu teslim günlük akışın kapanışını tek ekrana getirir: çıktı sonucu, bölge/banka
dağılımı ve manuel Netsis kabul/ret kaydı aynı operasyon bağlamında izlenir.
İlgili yetki, geçmiş ve entegrasyon testleri geçti. Kalan kabul gerçek günlük
işlemden sonra bu sonucun kullanıcı tarafından kaydedilmesidir.

## 3A — Gerçek ERP kabul matrisi

### 3A-1 — Hesaplar arası virman (tamamlandı)

Hesaplar arası virman; son onaylı tek sayfalı, 32 sütunlu şablonun
sayfa/başlık/hücre biçimini korur. Kaynak ve hedef banka kodu, yön, genel
referans, proje, tutar ve metin `00` Plas.Kodu yazımdan sonra denetlenir.

### 3A-2 — Havale ve FOM çıktıları (tamamlandı)

- Normal havale, toplu banka kodlu havale, hesaplar arası virman, FOM satış
  ve FOM tahsilat için tek bir kod tabanlı kabul matrisi oluşturuldu.
- Netsis profillerinde profil sabitleri, gerçek Excel tarihleri, para biçimi,
  zorunlu metin/kimlik alanları, banka kodu ve şablona bağlı kritik hücre
  biçimleri dosya yayımlanmadan önce kontrol edilir.
- FOM satış ve tahsilatında tam dosya adı, tek ve özgün sayfa adı,
  başlıklar, satır sayısı, her veri sütununun ikinci şablon satırındaki
  sayı biçimi ve metin kimlikleri kontrol edilir.
- Satış şablonunun ilk 16 alanı, özellikle müşteri/fatura/personel/ürün
  kodları ile tarih alanları, Psoft'un onaylı yapısına uygun olarak metin
  kalır. Personel kodunun baştaki sıfırları korunur.
- Profil yükleyicideki eski başlık tahmini kaldırıldı. Başlığında
  `Tutar` geçen bir alan artık kendiliğinden para biçimine çevrilmez;
  onaylı profilin açık `style` değeri tek otoritedir.
- Onaylı yerel şablonlar ve kontrol değerleri değiştirilmedi. Microsoft
  Excel ile beş gerçek çıktı türü ayrı ayrı üretildi ve kabul kapısından
  geçti; bu teknik kontrol Netsis/Psoft'un kullanıcı tarafından kaydedilen
  gerçek kabul sonucunun yerine geçmez.

### 3A-3 — Dosya bazlı gerçek ERP kabul kanıtı (tamamlandı)

- Kullanıcının Netsis/Psoft kabul veya ret kararı artık yalnız işleme değil,
  seçilen gerçek çıktı dosyasına bağlanır. İşlem tamamlandığında alınan
  SHA-256 parmak izi ve dosya boyutu kararla birlikte saklanır.
- Seçilmeyen, başka bir işleme ait, taşınmış, silinmiş veya üretimden sonra
  değiştirilmiş dosya için ERP sonucu kaydedilemez. Dosya içeriği işlem
  geçmişine kopyalanmaz.
- Bir işlem birden fazla ERP çıktısı üretmişse tek dosyanın kabulü tüm işlemi
  kabul edilmiş yapmaz. Ekranlar sonucu `sonuç yok`, `kısmi`, `tümü kabul`
  veya `en az biri reddedildi` olarak ortak kuralla hesaplar.
- Operasyon Merkezi, Geçmiş İşlemler, dönem eğilimleri ve Entegrasyonlar ekranı
  aynı dosya bazlı sonucu kullanır. Eski işlem düzeyi kabul kayıtları geriye
  uyumlu olarak okunmaya devam eder.
- Onaylı Excel şablonları, dosya adları, hücre biçimleri ve şablon kontrol
  değerleri bu aşamada değiştirilmedi.

### 3A-4 — ERP ret eğilimi (tamamlandı)

- Geçmiş İşlemler, seçili dönemde Netsis ve Psoft için en sık görülen iki ret
  nedenini kabul/ret özetinin yanında gösterir.
- Sayım, işlemde son durumda reddedilmiş ERP çıktılarının ön tanımlı kategori
  kodlarından yapılır. Aynı çıktı sonradan kabul edilirse eski ret sayılmaz.
- Bu görünüm bir otomatik düzeltme veya otomatik kabul mekanizması değildir;
  kullanıcının sorun tekrarını erken görüp ilgili çıktı profilini kontrol etmesi
  için karar desteğidir.
- Müşteri, IBAN, banka hareketi, Excel hücresi veya tutar bilgisi okunmaz ya da
  bu özet ekrana taşınmaz. Onaylı şablonlar değiştirilmez.

## 3B — ERP kalite sinyalinin operasyon yönetimine bağlanması (tamamlandı)

- Operasyon Merkezi'ndeki “ERP kalite sinyali” alanı son yedi günün Netsis ve
  Psoft kabul/ret sayısını, varsa en sık iki ret kategorisiyle birlikte gösterir.
- Bu alan Geçmiş İşlemler'deki dosya bazlı son karar hesabını aynen kullanır;
  tek dosyanın kabulü çoklu çıktılı işlemi tam kabul göstermez.
- Sinyal kullanıcıyı çıktı sözleşmesini veya aktarım ekranını kontrol etmeye
  yönlendirir. Otomatik düzeltme, otomatik aktarım veya otomatik kabul vermez.
- Finansal içerik, müşteri, IBAN, Excel satırı veya gerçek ERP hata metni bu
  özet içinde tutulmaz. Onaylı şablonlar değiştirilmez.
