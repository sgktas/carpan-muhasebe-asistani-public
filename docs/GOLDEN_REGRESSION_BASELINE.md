# Golden Regression Baseline

## Purpose

P1 golden testleri, Çarpan'ın mevcut muhasebe kararlarını P2 `ProcessingEngine`
ayrıştırması öncesinde sentetik ve karşılaştırılabilir sözleşmelere dönüştürür.
Excel binary'leri değil, karar ve muhasebe anlamı karşılaştırılır.

## Covered Behavior

- Normal MANİM havale, ödeme-onaylı ve referanslı karar dağılımı.
- Gerçek üretilmiş Netsis `.xls` dosyasının tekrar okunmuş semantic satırı.
- Maskeli `BTD**` cari kodu çözümü.
- Vergi numarası ve şubeli tahsilat eşleşmesinde para korunumu.
- Çözülemeyen hareketin Netsis satırı üretmemesi.
- Tekrar kaynak engeli.
- Tahsilat satırının ikinci operasyonda tekrar tüketilememesi.
- Banka mutabakatında birebir ve gruplanmış eşleşme.
- FOM tahsilat dönüşümünün satır ve toplam özeti.

## Intentionally Ignored

Geçici klasörler, mutlak yollar, Excel metadata/stilleri, dosya adları, çalışma
süreleri, log cümleleri, kullanıcı/makine bilgisi ve database satır kimlikleri
golden veriye girmez.

## Updating Goldens

Golden farkı önce muhasebe davranışı değişikliği olarak incelenmelidir. Yalnız
bilinçli iş kuralı değişikliği onaylandıktan sonra snapshot güncellenir; test
çalışırken snapshot asla yeniden yazılmaz.
