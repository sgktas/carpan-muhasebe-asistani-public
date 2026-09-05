# Çarpan Muhasebe Asistanı

PySide6 tabanlı MANİM → Netsis aktarım uygulaması.

## Çalıştırma

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python app/main.py
```

Windows'ta bu kurulum `pywin32` paketini de getirir. Terminalden çalıştırırken
`derle.bat` kullanmak gerekmez; önemli olan bağımlılıkları aktif `.venv` içine
`requirements.txt` üzerinden kurmaktır.

## Test

```powershell
python -m pytest -q
```

## Windows EXE

```powershell
derle.bat
```

PyInstaller paketindeki `config`, `templates` ve `assets` dosyaları yalnızca okunur.

Sistem verileri Windows'ta şu gizli uygulama klasöründe tutulur:

```text
%LOCALAPPDATA%\Carpan\MuhasebeAsistani\data\
```

- `processed_files.json`: başarıyla tamamlanan MANİM dosyalarının geçmişi
- `customer_mappings.json`: kullanıcı tarafından doğrulanan cari eşleştirmeleri

Kullanıcının açacağı Excel çıktıları gizli klasöre yazılmaz. Görünür çıktı yolu:

```text
Belgeler\Çarpan Muhasebe Asistanı\Çıktılar\
```

Her işlem bu klasör altında tarih-saat isimli ayrı bir alt klasöre kaydedilir.

Geliştirme/test amacıyla veri kökü şu ortam değişkeniyle değiştirilebilir:

```powershell
$env:MUHASEBE_ASISTANI_DATA_DIR="C:\MuhasebeAsistaniTest"
$env:MUHASEBE_ASISTANI_OUTPUT_DIR="C:\MuhasebeAsistaniCiktilari"
```


## Otomatik eşleştirme sırası

1. MANİM karşı hesap kodu
2. Açıklamadaki açık/maskeli müşteri kodu
3. Firma adıyla şubeli eşleştirme
4. Vergi/T.C. numarasıyla şubeli eşleştirme
5. Tahsilat toplamı ile kesin mutabakat
6. Yalnız belirsiz kayıtlar için manuel ekran

`111*11111111` ve `222-222222222` gibi tamamen örnek maskeli/ayrılmış müşteri kodları desteklenir. Zincir müşterilerde müşteri listesinin `Şube` alanı ile bölge önceliği uygulanır.

## İşlem güvenliği

- MANİM dosyaları, bütün çıktılar başarıyla üretildikten sonra işlenmiş olarak kaydedilir.
- Çıktılar önce geçici klasörde hazırlanır; writer hatasında yarım çıktı klasörü bırakılmaz.
- Eksik/geçersiz MANİM satırları müşteri eşleştirmesine girmez ve `GECERSIZ_MANIM_SATIRLARI_*.xls` raporuna yazılır.
- Pasif müşterilerin borç kapatma havaleleri için cari kod manuel girilebilir ve kullanıcı onayıyla aktarılabilir.
- Onaylı Netsis profilleri arayüzden değiştirilemez; özel formatlar ayrı kullanıcı profili olarak saklanır.
- Oluşan Netsis dosyası başlık, sayfa, satır sayısı, tutar toplamı, banka kodu ve kritik hücre biçimleri açısından otomatik doğrulanır.

## Excel çıktı biçimi

- Netsis havale çıktıları 27 sütunlu profil tanımından gerçek Excel 97–2003 biçiminde üretilir.
- Git dışında `templates/local/` altında şirket şablonu varsa Windows'ta Microsoft Excel COM motoru kullanılır.
- Windows üretim ortamında onaylı yerel şablon eksikse işlem durur; genel bir Excel dosyasına sessizce geçilmez.
- Çıktılar kaydedildikten sonra Windows salt-okunur niteliği açıkça temizlenir.
- Netsis'e aktarırken `.xls` dosyasını ZIP/sıkıştırılmış klasör içinden seçmeyin; önce normal klasöre ayıklayın.

## Çok günlük MANİM aktarımı

- MANİM dosyaları birden fazla işlem tarihi içeriyorsa ilk ve son tarih çıktı adına yazılır.
- Örnek dosya: `BODRUM_GARANTI_18-19.07.2026.xls`
- Örnek klasör: `2026-07-18_2026-07-19_10-30-00`
- Netsis satırları işlem tarih-saatine göre küçükten büyüğe sıralanır.

## Çıktı sırası ve bölge gruplaması

Windows Dosya Gezgini dosyaları ada göre sıraladığı için çıktı adlarına sabit sıra ön eki eklenir:

```text
01_BODRUM_...
02_FETHIYE_...
03_SOKE_...
04_MUGLA_...
05_ANTALYA_...
06_DENIZLI_...
07_AYDIN_...
08_NAZILLI_...
09_ODEME_ONAYLANDI_...
10_REFERANSLI_...
```

İnceleme ve geçersiz satır raporları varsa bunlar `07_` ve `08_` ön ekiyle en sonda görünür.

- Ödeme Onaylandı kayıtları tek sayfada Ayarlar > Bölge Yönetimi ekranındaki aktif bölge sırasına göre bloklar halinde yazılır.
- Her bölge bloğunda tarih/saat kronolojisi korunur.
- Referanslı dosyasındaki sayfa sırası aktif bölge sırasıyla aynıdır.
- Varsayılan aktif sıra Bodrum → Fethiye → Söke → Muğla → Antalya → Denizli → Aydın → Nazilli'dir.
- Yeni bölgeler Ayarlar > Bölge Yönetimi ekranından kod değişikliği gerektirmeden eklenebilir, düzenlenebilir veya pasifleştirilebilir.
- Tek bir MANİM dosyası birden fazla bölge içerebilir. Her satır önce banka ile `Kod - Şube` alanındaki hesap/IBAN değerinin ayırt edici son haneleri eşleştirilerek bölgeye ayrılır; eşleşme yoksa dosya adındaki bölge yedek olarak kullanılır.
- Bölge Yönetimi ekranında çıktı banka kodları ile MANİM hesap/IBAN son haneleri ayrı alanlarda tutulur.
- Satır bölgesi belirleme önceliği: banka + hesap/IBAN sonu → güncel müşteri listesindeki karşı müşteri kodu → tekil müşteri ünvanı/tabela adı → dosya adındaki bölge.
- Aynı müşteri adı birden fazla bölgeye işaret ediyorsa isimden otomatik karar verilmez.
- Açıklamada yıldız yerine `X` ayırıcıyla gelen cari kodlar desteklenir. Örnek: `MX11111111111` → `M11111111111`.

## Kurumsal arayüz ve tasarım sistemi (v12)

- Orijinal Çarpan logosu açık renkli sidebar üzerinde kendi kurumsal renkleriyle kullanılır.
- Marka renkleri, yüzeyler, butonlar, navigasyon, kartlar ve durum bileşenleri `app/ui/theme.py` içinde merkezileştirilmiştir.
- Sidebar iki katmana ayrılır:
  - Modüller
  - Yönetim
- MANİM sayfasında:
  - sürükle-bırak alanı,
  - klasik dosya seçici,
  - seçili dosya durumu,
  - işlem ilerlemesi,
  - işlem günlüğü
  aynı kurumsal bileşen sistemiyle sunulur.
- Küçük ekranlarda içerik üst üste binmez; sayfa dikey kaydırma alanına geçer.
- Giriş ekranı ana uygulamayla aynı logo, renk, tipografi ve form standardını kullanır.
- İşleme motoru ve Excel çıktı kuralları bu revizyonda değiştirilmemiştir.

## Modüler çekirdek ve Rapor Düzenleme modülü (v13)

Uygulama artık sabit sayfalardan oluşan tek amaçlı bir araç değildir. Modüller
`app/modules/registry.py` üzerinden kayıt edilir ve kullanıcının yerel
entitlement yetkilerine göre sidebar'a dinamik olarak eklenir.

Müşteri listesi dahil modüller:

```text
MODÜL 01 — MANİM Aktarma
MODÜL 02 — Rapor Düzenleme
MODÜL 05 — Müşteri Listesi
```

Ortak çekirdek hizmetleri:

- dinamik modül kaydı ve navigasyon,
- modül kimliği/sürümü/ikon sözleşmesi,
- görünür ortak çıktı klasörü,
- SQLite işlem geçmişi,
- modül bazlı işlem durumu ve özet kaydı,
- ileride çevrimiçi veya imzalı lisansa bağlanabilecek entitlement katmanı.

Yerel geliştirme sürümünde kayıtlı bütün modüller açıktır. Ticari lisans sistemi
eklendiğinde arayüz ve modül kodları değişmeden yalnız entitlement sağlayıcısı
değiştirilecektir.

### Rapor Düzenleme girdileri

Aynı döneme ait üç ham `.xlsx` raporu birlikte seçilir:

1. Ham müşteri listesi
2. Ham satış raporu
3. Ham tahsilat raporu

Dosya türleri dosya adına göre değil, Excel sütun başlıklarına göre otomatik
tanınır. Satış veya tahsilat raporuna şube bilgisi eklenebilmesi için ham müşteri
listesi zorunludur.

### Rapor Düzenleme çıktıları

Windows'ta normal işlem toplam beş dosya üretir:

```text
01_MUSTERI_LISTESI_DUZENLENMIS.xlsx
02_SATIS_RAPORU_DUZENLENMIS_<tarih>.xlsx
03_TAHSILAT_RAPORU_DUZENLENMIS_<tarih>.xlsx
ENT-Muhasebe_Entegrasyon(Satış_Faturaları).xls
ENT-Muhasebe_Entegrasyon(Tahsilatlar).xls
```

Satış ve tahsilat dosyaları, operasyon sistemindeki orijinal dosya adları ve
orijinal Excel sayfa adlarıyla üretilir. `.xlsx` tahsilat dosyasında ana sayfa
yalnız `TahsilatTipi=N / TahsilatTuru=1` kayıtlarını, `ŞUBELİLER` sayfası ise
MANİM eşleştirmesi için tüm kayıtları taşır. Orijinal `.xls` tahsilat şablonuna
yalnız N/1 kayıtları yazılır; fazladan `ŞUBELİLER` sayfası eklenmez.

Satış raporundaki `Fiyat` sütunu binlik ayırıcı açık ve üç ondalık basamaklı
sayı biçiminde kaydedilir. Git dışında `templates/local/` altında şirket
şablonları bulunursa Microsoft Excel COM ile doldurulur; bulunmazsa veri
içermeyen Excel 97–2003 çıktıları koddan üretilir.

## Veri güvenliği

Bu public depo gerçek müşteri, personel, banka hareketi veya şirket içi kod
verisi içermez. Gerçek dosyalar `local_data/`, `inputs/`, `outputs/` veya
`config/local/` altında tutulur ve Git tarafından izlenmez. Geliştirme ortamını
hazırladıktan sonra güvenlik kancasını etkinleştirmek için:

```powershell
.\scripts\setup_git_safety.ps1
```

Her commit ve GitHub kontrolünde `scripts/check_public_data.py` çalıştırılarak
metin dosyaları ile Excel şablonları hassas veri açısından taranır.

Uygulanan kesin kurallar `docs/RAPOR_DUZENLEME_KURALLARI.md` dosyasında
dokümante edilmiştir.

### İşlem geçmişi

Bütün modül işlemleri aşağıdaki SQLite veritabanına kaydedilir:

```text
%LOCALAPPDATA%\Carpan\MuhasebeAsistani\data\operations.sqlite3
```

Geçmiş İşlemler ekranı son 100 işlemin:

- işlemi yapan yerel kullanıcıyı,
- modülünü,
- başlangıç zamanını,
- durumunu,
- girdi/çıktı sayısını,
- temel işlem özetini

gösterir ve seçili işlemin çıktı klasörünü açar. Ayrıntı ekranında işlem olayları,
girdiler, çıktılar ve hata bilgisi izlenebilir. Uygulama beklenmeden kapanırsa yarım
kalan işlem bir sonraki açılışta ayrıca işaretlenir.

### Profesyonel çalışma temelleri

- Parasal karşılaştırmalar iki ondalıklı kesin değerlerle yapılır; çoklu havaleler yalnız toplamlar birebir eşitse otomatik birleşir.
- Uzun süren MANİM işlemleri arka planda çalışır; arayüz işlem sırasında kilitlenmez.
- Ayarlar ekranından eşleştirme hafızası, işlem geçmişi, bölge ayarları ve kullanıcı profilleri için yerel ZIP yedeği alınabilir.
- Uygulama hataları `%LOCALAPPDATA%\Carpan\MuhasebeAsistani\logs\uygulama.log` dosyasına dönüşümlü olarak kaydedilir.
- Bağımlılık sürümleri sabitlenmiştir; GitHub üzerinde her gönderimde testler ve veri güvenliği taraması otomatik çalışır.


## Rapor Düzenleme ile MANİM entegrasyonu

Rapor Düzenleme modülünün tahsilat çıktısı doğrudan MANİM Aktarma modülünde
kullanılabilir. Dosyada `ŞUBELİLER` sayfası varsa MANİM motoru şubeli
eşleştirme için bu tam veri sayfasını otomatik seçer. Tek sayfalı orijinal
tahsilat raporlarında ilk sayfa okunmaya devam eder.

MANİM Aktarma ekranı sabit bir MANİM dosya sayısı beklemez; aynı işlemde bir
veya daha fazla MANİM raporu verilebilir. Ham FOM müşteri listesi, bağımsız
**Müşteri Listesi** modülünde düzenlenir ve yerel hafızaya alınır; MANİM
aktarımı bu hazırlanmış sürümü kullanır. MANİM'deki açık karşı hesap kodu
hafızadaki listede yoksa kayıt otomatik eşleştirilmez; diğer işlemler durmadan
devam eder ve ilgili kayıt manuel eşleştirme ekranında kontrol edilir.

### Havale çıktı şablonları

MANİM Aktarma > **Aktarım Ayarları** sekmesinden havale şablonu seçilir.
Mevcut şablon bölge ve banka için ayrı dosya üretmeye devam eder. **Netsis —
Toplu Banka Kodlu Havale** şablonu ise her bölge için tek dosya üretir; Garanti,
Yapı Kredi ve Ziraat satırlarının `Banka Hes.Kodu(*)` alanına bölge ayarlarındaki
ilgili BM kodu otomatik yazılır.

### Hesaplar arası virman çıktısı

MANİM'de **Referanslı** durumundaki negatif hareketlerden yalnız açıklamasında
virman/giden hesap transferi işareti bulunan ve hedef şirket hesabı Bölge
Yönetimi'ndeki hesap/IBAN son haneleriyle kesin eşleşen kayıtlar ayrılır. Her
kaynak bölge için tek `HESAPLAR_ARASI_VIRMAN_*.xlsx` dosyası oluşur; o bölgenin
tüm kaynak bankaları aynı dosyada yer alır. Kaynak BM kodu `Banka Hes.Kodu(*)`,
hedef BM kodu `Banka Hesap Kodu(*)` alanına yazılır ve yön değeri giden işlem
için `1` olur. Hedefi belirsiz olan veya şirket dışı ödemeler otomatik aktarılmaz;
mevcut Referanslı inceleme dosyasında kalır.

Virman çıktısı yalnız onaylı `HESAPLAR ARASI VİRMAN TOPLU.xlsx` şablonunun yerel
birebir kopyasından üretilir. Sayfa adları, 32 sütunlu başlık dizilimi ve çalışma
kitabı yapısı doğrulanmadan çıktı başarılı sayılmaz.


## Revize 18 — Çıktı Klasörü ve FOM Adlandırması

- MANİM çıktıları `MANİM AKTARMA - <Excel işlem tarihi>` klasöründe oluşturulur.
- Rapor düzenleme çıktıları `FOM AKTARMA - <Excel işlem tarihi>` klasöründe oluşturulur.
- Modülün görünen adı `FOM Rapor Düzenleme` olarak değiştirilmiştir.
- Aynı tarih için tekrar işlem yapılırsa klasör adına `_2`, `_3` gibi benzersiz ek gelir.
