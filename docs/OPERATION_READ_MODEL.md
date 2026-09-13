# Operation Read Model

## Amaç

`OperationReadModel`, mevcut yerel kalıcılık servislerinin salt-okunur bir
projeksiyonudur. “Bu Çarpan operasyonunun gözlemlenebilir tam durumu nedir?”
sorusuna cevap verirken çelişen gerçekleri gizlemez veya tek bir başarı
durumuna indirgemez.

Model yeni bir source of truth değildir. Hiçbir SQLite/JSON şemasını veya
kalıcılık sırasını değiştirmez.

## Ham alanların kaynakları

| Alan | Yetkili kaynak |
|---|---|
| operation kimliği, firma, modül | `OperationHistory` |
| history durumu ve zamanları | `OperationHistory` |
| history çıktı yolları | `OperationHistory` |
| publication durumu, ID, kaynak hash'leri ve çıktı yolları | `PublicationJournal` |
| review grup durumu ve üyeleri | `ReviewQueue` |
| aktif review phase | `ReviewWorkflow` verildiğinde workflow |
| normal işlenmiş-kaynak işareti | `ProcessedFilesLog` |
| fiziksel dosyanın mevcut olması | dosya sistemi |

Tahsilat kullanım defterinde operation kimliği bulunsa da mevcut public API bir
operation için tüketim satırı veya sayısı okumaz. P3-C bu nedenle doğrudan SQL
okuması veya tahmini bir consumption alanı eklemez.

## Türetilmiş tutarlılık modeli

Durumlar:

- `CONSISTENT`: bilinen bir tutarlılık veya dikkat nedeni yoktur.
- `ATTENTION`: gerçek durumlar korunmuştur; bir veya daha fazla açık dikkat
  nedeni vardır.
- `RECOVERY_REQUIRED`: en az bir publication kaydı hâlâ `PUBLISHED` durumundadır.

Makine tarafından okunabilir neden kodları:

- `publication_pending_commit`
- `history_publication_mismatch`
- `review_pending`
- `output_missing`
- `processed_source_missing`

Bu nedenler muhasebe sonucu üretmez. Yalnız mevcut store durumları arasındaki
operasyonel ilişkiyi açıklar.

## Bilinen split-state'ler

- Journal `COMMITTED`, history `INTERRUPTED`: iki gerçek de ayrı alanlarda
  korunur; sonuç `ATTENTION` ve `history_publication_mismatch` olur.
- Journal `PUBLISHED`: history durumu ne olursa olsun publication gerçeği
  korunur; sonuç `RECOVERY_REQUIRED` olur.
- Review açık, history farklı: review grubu/fazı ve history durumu birlikte
  gösterilir; `review_pending` eklenir.
- `operation_id=None`: sahte bir operation kimliği üretilmez. Bu orphan kayıtlar
  operation düzeyindeki view ile birleştirilemez.
- Kayıtlı çıktı yolu eksik: hash doğrulaması yapılmadan yalnız dosyanın mevcut
  olmadığı gösterilir.

## Salt-okunur olma nedeni

Publication, retry, review, tahsilat tüketimi ve processed-files farklı güvenlik
amaçlarına ve transaction sınırlarına sahiptir. Read model bunların hiçbirinde
`INSERT`, `UPDATE`, `DELETE`, commit, recovery approval veya status transition
yapmaz. İlgili store örnekleri dışarıdan hazır olarak verilir ve yalnız mevcut
public read API'leri kullanılır.

## Fiziksel birleştirmenin ertelenmesi

P3-B; journal, review, ledger, cache, mapping ve processed-files arasında bugün
kabul edilen kısmi hata durumlarını sabitledi. Veritabanlarını şimdi taşımak,
retry/idempotency davranışını ve eski yerel veriyi gereksiz riske atar. P3-C
önce tek ve açıklanabilir bir okuma sözleşmesi sağlar; fiziksel birleştirme ayrı
bir migration kararıdır.

## P3-D UI sözleşmesi

Operasyon Merkezi P3-D'de seçili operasyon için bu sözleşmeye bağlanmıştır:

- ham `history_status`, publication ve review alanlarını ayrı göstermeli;
- `consistency_status` değerini tek başına muhasebe başarısı gibi sunmamalı;
- `attention_reasons` kodlarını kullanıcı dilindeki kontrollü açıklamalara
  çevirmeli;
- `RECOVERY_REQUIRED` durumunda mevcut açık kurtarma akışını kullanmalı;
- read model üzerinden hiçbir recovery veya workflow yazma işlemi yapmamalı;
- `None` operation kimlikli kayıtları sahte operasyonlarla birleştirmemelidir.

Yeni kompakt tutarlılık kartında history, publication, açık review sayısı,
fiziksel çıktı varlığı ve processed-source durumu birlikte gösterilir.
`consistency_status` yalnız kart başlığı/severity seçiminde; kararlı reason
kodları ise kontrollü Türkçe açıklamalarda kullanılır. Özellikle
`processed_source_missing` veri kaybı veya işlem başarısızlığı olarak sunulmaz;
`output_missing` yalnız kayıtlı fiziksel yolun bulunamadığını söyler.

P3-D performans sınırı olarak read model her liste satırı için çağrılmaz.
OperationHistory'den zaten alınan firma-kapsamlı operasyonlar seçim kutusuna
konur ve yalnız kullanıcının seçtiği operasyon için birleşik görünüm hesaplanır.
Bu nedenle N+1 store taraması oluşmaz.

Doğrudan store okumaları şimdilik korunur:

- genel metrikler, haftalık özet, ERP sonuçları ve öncelikli liste
  `OperationHistory` üzerinden devam eder;
- kurtarma tablosu ve mevcut onay eylemi doğrudan `PublicationJournal`
  kullanmaya devam eder;
- ayrıntılı görevler ve tüm workflow yazıları `ReviewBoard` /
  `ReviewWorkflow` içinde kalır.

Bu ilk UI geçişi aynı görünür tutarlılık sonucunu iki ayrı yerde hesaplamaz;
birleşik durum kartının tek hesap kaynağı `UnifiedOperationView`'dır.

## Sınırlamalar

- Tek-operation lookup mevcut public store API'leri üzerinden firma kapsamlı
  kayıtları tarar. P3-D toplu ekran entegrasyonunda N+1 sorgu oluşturmadan önce
  ayrı, bounded batch-read ihtiyacı değerlendirilmelidir.
- Publication journal dosya hash'i saklamadığından model içerik değişikliğini
  değil yalnız fiziksel dosya varlığını kontrol eder.
- Consumption state operation düzeyinde gösterilmez.
- Processed-files firma kimliğini kaydın içinde taşımaz; firma ayrımı aktif
  workspace dosya sınırıyla sağlanır.
- Operasyon Merkezi'nin toplu tabloları henüz read model'e geçirilmemiştir.
  Daha sonraki bir geçiş, bounded batch-read API olmadan her satır için tekil
  lookup çağırmamalıdır.
