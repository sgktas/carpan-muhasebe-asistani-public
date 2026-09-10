# MANİM İşleme Mimarisi

MANİM aktarımı, tek bir büyük sınıf yerine birbirinden ayrı sorumluluklarla
çalışır. `ProcessingEngine` bu parçaları sıraya koyan koordinatördür; iş
kurallarının ayrıntılarını kendi içinde tekrar etmez.

## İşlem hattı

İşçi başlamadan `manim_configuration.py` bölge ve etkin profil ayarlarını
değiştirilemez bir yürütme kopyasına alır. Aynı kopya işlem geçmişindeki
sürüme bağlanır; aşağıdaki servisler o işlem boyunca bu ayarı kullanır.
Ayrıntılar ve sonraki otomasyon sırası `OPERASYON_OTOMASYONU_MIMARISI.md` içindedir.

1. `ManimInputClassifier`
   - Seçilen Excel dosyalarını MANİM, tahsilat ve müşteri listesi olarak tanır.
   - Dosya adıyla birlikte sütun başlıklarını da kanıt olarak kullanır.
2. `ManimRegionResolver`
   - Bölgeyi önce banka hesabından, sonra tekil müşteri kodundan, sonra tekil
     müşteri adından ve son olarak dosya adından belirler.
   - Birden fazla bölgede bulunan zincir müşteri adı tek başına kesin bölge
     kanıtı kabul edilmez.
3. `MovementRouter`
   - Ödeme Onaylandı, Kural Çalıştı, Referanslı, aynı banka virmanı, normal
     havale ve inceleme kararlarını tek noktadan verir.
4. `HavaleProcessor`
   - Normal gelen havaleyi müşteri ve tahsilat kayıtlarıyla eşleştirir.
5. `CombinedBankMovementMatcher`
   - Aynı gün, bölge, banka ve tahsilat havuzuna ait birden fazla havaleyi
     birlikte değerlendirir. Toplam kuruşu kuruşuna eşitse otomatik aktarır;
     farklıysa tek bir toplu kayıt olarak manuel incelemeye bırakır.
6. `ManualResolutionService`
   - Eşleştirme ekranındaki Havale, Ödeme Onaylandı, Referanslı ve Atla
     kararlarını uygular.
   - Negatif Ödeme Onaylandı, fazla tutar, eksik BM kodu ve kısmi eşleştirme
     kurallarını merkezi biçimde doğrular.
7. `ManimOutputService`
   - Kayıtları bölge/banka ve tarih sırasına dizer.
   - Yalnız seçili ve onaylı çıktı profillerini kullanır.
   - Dosyaları önce geçici klasörde tamamlar; tümü başarılı olunca nihai
     klasörü görünür hale getirir.

## Değişmezler

- Onaylı şablon dosyaları okunur; kaynak şablonun içine veri yazılmaz ve şablon
  yeniden oluşturulmaz.
- İşlenmiş dosya geçmişi ve eşleştirme hafızası ancak tüm çıktılar başarıyla
  tamamlandıktan sonra güncellenir.
- Bölge bulma, hareket rotası ve manuel karar kuralları farklı katmanlarda
  birbirinin yerine geçirilmez.
- UI yalnız kullanıcıdan karar toplar; mali doğrulama UI içine yazılmaz.
- Yeni bir çıktı veya rota, kendi sözleşmesi ve regresyon testleri olmadan ana
  işleme motoruna eklenmez.
