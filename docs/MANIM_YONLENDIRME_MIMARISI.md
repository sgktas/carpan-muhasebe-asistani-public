# MANİM Hareket Yönlendirme Mimarisi

MANİM satırlarının çıktı kararı `MovementRouter` üzerinden tek noktadan verilir.
Karar; rota, sabit karar kodu, kullanıcıya gösterilecek neden, belirsizlik durumu
ve varsa rotaya özel çıktı kaydını birlikte taşır.

## Karar önceliği

1. `Ödeme Onaylandı`
   - Pozitif tutar doğrudan ödeme onaylandı çıktısına gider.
   - Negatif tutar manuel incelemeye gider.
2. `Kural Çalıştı`
   - Bölgesel kural çalıştı çıktısına gider.
3. `Referanslı`
   - Pozitif ve açıklamasında `ROTA`/`YATAN PARA` bulunan kayıt manuel incelemeye gider.
   - Negatif kayıt yalnız kaynak ve hedef banka aynıysa, hedef şirket hesabı kesin
     bulunuyorsa hesaplar arası virman olur.
   - Farklı bankaya giden hareket ve hedefi belirsiz hareket referanslıda kalır.
4. Diğer dekont durumları
   - Normal müşteri havalesi eşleştirme sürecine gider.

Manuel ekranda Referanslı olarak onaylanan kayıt da aynı referanslı yönlendirme
kuralından yeniden geçirilir. Böylece otomatik ve manuel akış farklı karar vermez.

## Yeni rota ekleme sözleşmesi

Yeni bir hareket türü eklenirken aşağıdaki parçalar birlikte hazırlanmalıdır:

1. Hareketi kesin ve belirsiz olarak ayıran bağımsız algılayıcı.
2. `MovementRoute` değeri ve sabit karar kodları.
3. `MovementRouter` içindeki açık öncelik noktası.
4. Rotaya özel kayıt modeli ve onaylı çıktı profili/şablonu.
5. Çıktı sözleşmesi: dosya biçimi, sayfa, başlık, kritik kodlar ve tutar kontrolü.
6. Otomatik, belirsiz ve yanlış-pozitif senaryolarını kapsayan regresyon testleri.

Farklı bankalar arası transfer rotası, kullanıcı onaylı şablon gelene kadar aktif
edilmez. Bu hareketler mevcut Referanslı çıktıda kalır.
