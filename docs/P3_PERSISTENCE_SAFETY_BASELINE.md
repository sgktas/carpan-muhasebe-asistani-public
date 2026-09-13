# P3 Persistence Safety Baseline

Bu belge P3-C öncesindeki mevcut MANİM kalıcılık davranışını tanımlar. Bir
yeniden tasarım veya ideal transaction modeli değildir. P3-B testleri bu
davranışın istemeden değiştirilmesini engeller.

## Başarılı kalıcılık sırası

Fiziksel Excel çıktıları yazılıp çıktı kalite kontrolü tamamlandıktan sonra sıra
şöyledir:

1. publication journal `PUBLISHED`
2. review queue grupları
3. tahsilat consumption ledger
4. müşteri listesi cache'i
5. manuel mapping state
6. processed-files kaydı
7. publication journal `COMMITTED`

Bu adımlar tek bir veritabanı transaction'ı değildir. Her SQLite/JSON/dosya
sınırı kendi atomikliğine sahiptir.

## A–G kısmi hata matrisi

| Hata noktası | Kalıcılaşmış durum | Henüz yazılmamış durum |
|---|---|---|
| A — publish | Fiziksel çıktı mevcut olabilir | journal, review, ledger, cache, mapping, processed-files |
| B — review | journal `PUBLISHED` | ledger, cache, mapping, processed-files, final commit |
| C — consumption | journal `PUBLISHED`, daha önce eklenen review grupları | ledger, cache, mapping, processed-files, final commit |
| D — customer cache | journal, review, ledger | cache, mapping, processed-files, final commit |
| E — mapping | journal, review, ledger, cache | mapping, processed-files, final commit |
| F — processed-files | journal, review, ledger, cache, mapping | processed-files, final commit |
| G — final commit | journal hâlâ `PUBLISHED`; review, ledger, cache, mapping ve processed-files yazılmıştır | `COMMITTED` geçişi |

Birden fazla review grubu ayrı çağrılarla yazılır. Daha sonraki bir grup hata
verirse önceki gruplar korunur; sonraki persistence aşamaları başlamaz.

## Restart ve split-state

MANİM motorunun kalıcılaştırması ile `OperationHistory.complete()` aynı
transaction değildir. Motor journal kaydını `COMMITTED` yapmış olsa bile UI
history tamamlama çağrısı hiç çalışmayabilir veya hata verebilir. Böyle bir
işlem history tarafında `RUNNING` kalabilir ve lease süresi dolduktan sonraki
başlangıçta `INTERRUPTED` olarak kurtarılır. Aynı operation ID için journal
durumu `COMMITTED` kalır.

Bu, P3-B tarafından belgelenen mevcut bir split-state'tir; P3-B bunu düzeltmez.

## Retry ve idempotency garantileri

- `processed_files.json`, aynı MANİM hash'i için normal mükerrer uyarısı verir.
- `PUBLISHED` journal kaydı aynı kaynağın sessiz yeniden yayınlanmasını durdurur.
- Kullanıcı `approve_retry()` ile açık kurtarma izni vermeden tekrar çalıştırma
  mümkün değildir.
- Tahsilat ledger'ı kaynak hash/sayfa/satır/tutar üzerinden çift tüketimi
  engeller.
- Exact-source consumption transferi yalnız aynı eksiksiz kaynak kümesine ait
  `COMMITTED` operation ID'leri için yapılır.
- Ledger yazıldıktan sonra journal commit öncesinde hata oluşursa kurtarma onayı
  publication engelini kaldırır, fakat kısmi operation `COMMITTED` olmadığı için
  consumption yeni operasyona taşınmaz. Mevcut tüketim çift kullanımı engellemeye
  devam eder.
- Bozuk `processed_files.json` boş kayıt gibi okunur; buna rağmen mevcut
  `PUBLISHED` journal kaydı sessiz yeniden yayını durdurur.
- Kalıcı MANİM akışı bugün `operation_id=None` ile çalışabilir. Journal, review
  ve ledger bu durumda null operation kimliği saklar.

## Fiziksel çıktı riski

Publication journal çıktı yollarını saklar; dosya hash'i veya yeniden doğrulama
yapmaz. `PUBLISHED` çıktı sonradan silinse bile kurtarma kaydı listelenir.
`COMMITTED` çıktı silindiğinde veya içeriği değiştiğinde journal bunu ayrıca
tespit etmez. Bu P3-B'de kabul edilen mevcut risk ve P3-C read modelinde görünür
kılınabilecek bir boşluktur.

## Kabul edilen mevcut kısmi durumlar

- Diskte çıktı var, journal kaydı yok.
- Journal `PUBLISHED`, review hiç yok veya kısmen var.
- Journal `PUBLISHED`, tahsilat tüketilmiş fakat cache/mapping/processed eksik.
- Journal `PUBLISHED`, processed-files dahil tüm yerel etkiler yazılmış fakat
  final journal commit yok.
- Journal `COMMITTED`, OperationHistory `RUNNING` veya restart sonrası
  `INTERRUPTED`.
- İnceleme workflow'u açıkken operation history başarısız/yarım görünebilir.

## P3-C sınırı

P3-C şunları yapabilir:

- mevcut store'ları salt okunur biçimde birleştiren unified operation read model
  eklemek;
- split-state ve fiziksel çıktı riskini kullanıcıya görünür kılmak;
- UI okumalarını aşamalı olarak bu facade'a taşımak.

P3-C şunları değiştirmemelidir:

- yukarıdaki kalıcılık sırası;
- retry/recovery onayı;
- tahsilat tüketim hesabı veya exact-source kuralı;
- review workflow geçişleri;
- mevcut SQLite/JSON dosya biçimleri;
- operation kimliği üretimi;
- MANİM, Netsis, FOM veya muhasebe kuralları;
- mevcut kısmi durumları rollback ile gizlemek.
