# Rapor Düzenleme Modülü — Kesin İş Kuralları

Bu belge, `RAPOR DÜZENLEME MODÜLÜ.zip` içindeki ham dosyalar, elle düzenlenmiş
doğru örnekler ve orijinal Excel 97–2003 şablonları karşılaştırılarak çıkarılan
kuralları tanımlar.

## 1. Dosya tanıma

Dosya türü dosya adından değil, ilk satırdaki sütun başlıklarından belirlenir.

- Müşteri: `Şube`, `Müşteri Sayısı`, `Müşteri Kodu`, `Vergi Numarası`
- Satış: `MüşteriKodu`, `FaturaNo`, `ÜrünKodu`, `NetFiyat`
- Tahsilat: `MusteriKodu`, `BelgeNo`, `TahsilatTipi`, `Tutar`

Aynı türden iki dosya seçilirse işlem durdurulur. Satış veya tahsilat için şube
üretileceğinden ham müşteri listesi aynı işlemde zorunludur.

## 2. Müşteri listesi

### Çıktı sütunları ve sırası

```text
Müşteri Sayısı
Müşteri Kodu
Şube
Tabela Adi
Ünvan
Vergi Dairesi
Vergi Numarası
Tekel No
SR-Rota
Banka
Ödeme Tipi
Faks No
Risk Limiti
Etiket
Telefon
Kredi Limiti
Fiyat Listesi
ERP Kodu
EFatura
E-fat-Tip
Vergi Tipi
Hero Sınıfı
Dış Kay.Sip.Kod
```

Referans çıktıda A sütunu boştur; başlıklar ve veri B sütunundan başlar.

### Şube dönüşümü

Aşağıdaki iki koşul birlikte sağlanıyorsa şube değiştirilir:

```text
Şube = SIMSEK-AYDIN
ve
SR-Rota içinde AYDIN-DD-02 veya AYDIN-WHS-02 bulunur
```

Yeni değer:

```text
Şube = SIMSEK-NAZILLI
```

Diğer satırlar değişmeden korunur.

## 3. Satış raporu

### Çıktı sütunları ve sırası

```text
MüşteriKodu, FaturaNo, Tarih, KDV, PersonelKodu, ÖdemeTipi,
ÜrünKodu, FOC, Tabela Adı, Vergi Dairesi, Vergi No,
İlk Matbu No, Fatura Kodu, İrsaliye Kodu, İrsaliye Numarası,
İrsaliye Tarihi, Miktar, Fiyat, İskonto1, İskonto2,
ToplamKDV, EklenenKDV, Vade, TuketiciFiyati, NetFiyat
```

Sonuna başlıksız `Şube` sütunu eklenir.

### Dönüşümler

- Şube, temiz müşteri listesindeki `Müşteri Kodu` eşleşmesinden alınır.
- `ÜrünKodu = 112064` ise:
  - `Fiyat = NetFiyat / Miktar`
  - `İskonto2 = 0`
- `Vade` boşsa `0` yapılır.
- Başka ürün kodlarında fiyat ve iskonto değerleri değiştirilmez.
- `Fiyat` sütunu sayı biçiminde, binlik ayırıcı açık ve 3 ondalık basamakla gösterilir.

## 4. Tahsilat raporu

### Çıktı sütunları

Ham 17 sütun aynı sırada korunur ve sonuna başlıksız `Şube` sütunu eklenir.

### Ana sayfa

Yalnız aşağıdaki iki koşulu birlikte sağlayan kayıtlar bulunur:

```text
TahsilatTipi = N
TahsilatTuru = 1
```

### ŞUBELİLER sayfası

- Ham tahsilat raporundaki bütün kayıtlar yer alır.
- Her satıra müşteri kodundan şube eklenir.
- Otomatik filtre açıktır.
- Metin içindeki literal `_x0009_` ifadeleri gerçek sekme karakterine çevrilir.

### Bulunamayan müşteri kodu

Müşteri kodu müşteri listesinde yoksa sistem rastgele şube seçmez:

```text
Şube = #N/A
```

Bulunamayan satır sayısı işlem günlüğüne ve işlem geçmişi özetine yazılır.

## 5. Orijinal şablonlar

### Satış şablonu

Temizlenmiş satış satırları şablonun ilk sayfasına ikinci satırdan itibaren
yazılır. Şablonun başlık ve belge yapısı korunur.

### Tahsilat şablonu

- Yalnız N/1 kayıtları orijinal tahsilat sayfasına yazılır.
- Orijinal `.xls` şablona `ŞUBELİLER` veya başka ek sayfa eklenmez.
- Tüm tahsilat kayıtları yalnız düzenlenmiş `.xlsx` dosyanın `ŞUBELİLER`
  sayfasında tutulur; MANİM modülü bu sayfayı kullanır.

### Dosya ve sayfa adları

```text
02_SATIS_RAPORU_DUZENLENMIS_<tarih>.xlsx
03_TAHSILAT_RAPORU_DUZENLENMIS_<tarih>.xlsx
ENT-Muhasebe_Entegrasyon(Satış_Faturaları).xls
ENT-Muhasebe_Entegrasyon(Tahsilatlar).xls
```

Düzenlenmiş `.xlsx` dosyaları kaynak raporun sayfa adını korur. Orijinal
`.xls` şablon çıktıları ise kaynak/orijinal raporlardaki 31 karakterlik Excel
sayfa adlarıyla kaydedilir.

Her iki şablon çıktısı Microsoft Excel ile `FileFormat=56` kullanılarak `.xls` kaydedilir.
Şablon çıktısı için Windows ve kurulu Microsoft Excel gerekir.
