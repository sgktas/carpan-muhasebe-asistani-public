# Operasyon arayüzü — 11 Eylül 2026

## Uygulanan kapsam

- MANİM ana eylemleri (önizleme ve çıktı hazırlama) sonuç eylemlerinden ayrıldı.
- MANİM, FOM ve banka mutabakatı girdi alanları açılıp kapatılabilir; sonuçtan sonra daraltılır.
- FOM ve banka mutabakatında dosya tanıma ve rapor hazırlama arka planda çalışır. Sonuçlar ve widget değişiklikleri ana arayüz iş parçacığına döner.
- İşlem sırasında tekrar başlatma, dosya değiştirme, çıkış ve oturum kapatma engellenir. Hata sonrası kontroller yeniden kullanılabilir.
- FOM çıktı adları ve kontrol bekleyen müşteri sayısı sonuç özetinde gösterilir. Banka mutabakatında sonuç, günlükten önce gelir.
- Adım kartları dar ekranda iki sütuna geçer. MANİM önizlemesi yapılmamışsa yapılmış gibi tamamlandı gösterilmez.
- Geçmiş ve dönem özetleri yalnız son 100 kayıtla sınırlı değildir; mevcut firma filtresi korunur.

## Doğrulama

Son birleşik koşum: 85 test geçti (yerel arayüz, operasyon geçmişi/merkezi/dönemleri, FOM motoru, banka modülü, MANİM motoru ve simülasyon). Dört mevcut Qt filtre API kullanım uyarısı var. Uzun çalışma alanı yolunda iki Windows dizin taşıma erişim hatası görüldü; kısa ve izole geçici dizinde aynı birleşik paket tamamen geçti.

`tests/test_local_workflow_ui.py`: ana arayüz zamanlayıcısının uzun işlem sırasında çalışması, sonuçların ana iş parçacığına dönmesi, tekrar başlatma engeli, hata sonrası yeniden deneme, FOM dosya taraması, 100 kaydı aşan geçmiş ve üç modülün 760/1100/1440 piksel içerik genişliğinde taşma kontrolü.

İsteğe bağlı `CARPAN_UI_SCREENSHOT_DIR` ile boş ve örnek verili sonuç sayfaları yakalanır. Görseller sentetik veridir; gerçek finans verisi ya da Netsis kabul testi değildir. Windows offscreen testinde Segoe UI fontları açıkça yüklenir.

Referans yaklaşım: Ramp mutabakat raporu (https://support.ramp.com/reconciliation-report-for-quickbooks-online/) ve Mercury Insights (https://mercury.com/insights). Özet → ayrıntı hiyerarşisi referans alındı; marka/tasarım kopyalanmadı.

## Sınırlar

Onaylı Excel şablonları, kontrol değerleri, hücre biçimleri ve çıktı sözleşmeleri değiştirilmedi. Gerçek Netsis/SQL/API aktarımı eklenmedi. ZIP/EXE hazırlanmadı.

Bu çalışma tüm ürün mimarisinin veya tüm ekranların tamamlandığı anlamına gelmez. İnceleme üç günlük operasyon ekranına odaklanır; gerçek günlük dosyalarla uzun süreli kullanım ve farklı Windows ekran ölçekleri ayrıca doğrulanmalıdır.
