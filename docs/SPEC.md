# Çarpan Muhasebe Asistanı — Modüler Ürün Spesifikasyonu

## Çekirdek

Çekirdek, muhasebe iş kurallarını doğrudan içermez. Şunları sağlar:

- modül kaydı ve dinamik navigasyon,
- entitlement kontrolü,
- kullanıcıya görünür ortak çıktı alanı,
- kalıcı SQLite işlem geçmişi,
- ortak kurumsal UI bileşenleri,
- veri/kaynak/çıktı yollarının ayrılması.

## Modül sözleşmesi

Her modül en az şu metadataları sağlar:

```text
module_id
name
nav_label
version
icon_name
badge
description
page_factory
```

`module_id` kalıcı lisans ve geçmiş anahtarıdır; ekranda görünen isim değişse bile
değiştirilmemelidir.

## Mevcut modüller

### manim_transfer

MANİM ve tahsilat verilerini bölge/banka bazında Netsis havale çıktılarına
dönüştürür. Referanslı negatif hareketlerde hedef şirket hesabı kesin
belirlenen hesaplar arası virmanları da kaynak bölge bazında tek, çok bankalı
Netsis XLSX çıktısına ayırır; belirsiz hareketleri Referanslı incelemede tutar.

### report_editing

Ham müşteri, satış ve tahsilat raporlarını temizler; standart `.xlsx` çıktılar
ve gerçek Excel 97–2003 şablon çıktıları üretir.

## Lisans hazırlığı

Geliştirme sürümünde `local_development_entitlements` bütün kayıtlı modülleri
açar. Ticari sürümde aynı `EntitlementSet.allows(module_id)` sözleşmesi:

- imzalı çevrimdışı lisans,
- aktivasyon sunucusu,
- modül aboneliği,
- paket/bundle lisansı

ile beslenebilir. Modül sayfaları ve sidebar bunun için yeniden yazılmamalıdır.

## İşlem geçmişi

`operations` tablosu:

- module_id
- module_name
- status
- started_at
- completed_at
- input_files_json
- output_files_json
- summary_json
- error_message

alanlarını tutar. Modül işlemleri `RUNNING` olarak başlar ve `SUCCESS`,
`PARTIAL` veya `FAILED` durumuyla kapanır.
