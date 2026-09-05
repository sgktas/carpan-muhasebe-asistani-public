# Kalıcı kullanıcı talimatı: orijinal çıktı şablonlarını koru

Kullanıcı açıkça istedi: **Netsis şablonunu kesinlikle bozma; yalnızca verilen
ve onaylanan orijinal şablonları kullan.** Bu kural her revize ve paket için geçerlidir.

- Normal havale `templates/local/netsis_template.xls` dosyasını kullanır.
  Bu, kullanıcının verdiği `NETSİS AKTARMA.xls` dosyasının birebir kopyasıdır.
- Toplu banka kodlu havale `templates/local/netsis_toplu_template.xls`
  dosyasını kullanır. Bu şablon, kullanıcının 4 Eylül 2026 tarihinde onayladığı
  `01_BODRUM_03092026.xls` düzeninden yalnız işlem verileri temizlenerek alınmıştır.
  Tek sayfası `Sheet1`'dır; `Muh.Ref.Kod(*)` sabiti `G01`'dir. Tarih, cari kod,
  tutar ve masraf tutarı hücre biçimleri bu onaylı dosyadaki gibi korunur.
- Toplu havale ve FOM çıktılarında da mevcut onaylı yerel şablonları koru.
- Başlıkları, sütun sırasını, sayfa adını, sütun genişliklerini ve mevcut
  biçimlendirmeyi değiştirme. Tutar sütunlarının binlik ayraçlı, iki ondalıklı
  sayısal biçimini yeni veri satırlarında da koru.
- Hesaplar arası toplu virman çıktısı
  `templates/local/netsis_virman_toplu_template.xlsx` dosyasını kullanır.
  Bu, kullanıcının 6 Eylül 2026 tarihinde onayladığı şablonun yalnız dolu
  `Sheet1` sayfası bırakılmış güncel sürümüdür. Kaynak banka kodu A, hedef
  banka kodu H, yön değeri 1 ve tutar O sütunundadır. Plas.Kodu U sütununda
  metin olarak `00` görünmelidir; sayısal `0.00` biçimi kullanılmaz.
- Kaynak şablonların içine veri yazma, yeniden kaydetme veya başka Excel
  biçimine dönüştürme. Yalnız ayrı çıktı dosyasındaki işlem verileri değişebilir.
- Şablon eksikse genel Excel üreterek devam etme. Önce orijinal dosyayı geri koy.
- Kaynak paketini `scripts/package_release.py` ile oluştur. EXE'yi
  `muhasebe_asistani.spec` ile derle. Her iki işlem şablon doğrulamasından geçmelidir.
- `config/local/template_checksums.json` onaylı dosyaların kontrol değerlerini
  tutar. Kontrol başarısız olursa işlemi durdur; hatayı geçirmek için kontrol
  değerlerini yeniden hesaplayıp değiştirme. Kullanıcı açıkça yeni şablon
  onaylamadan şablon veya doğrulama değeri değiştirilemez.
- Yerel şablonlar ve şirket ayarları kullanıcıya verilen özel paketlerde bulunur;
  public GitHub deposuna müşteri verisi, gerçek şablon veya yerel ayar ekleme.

Kullanıcı istemedikçe yeni ZIP/EXE oluşturma. Yeni paket istendiğinde şablonların
paketin içine eksiksiz girdiğini ve kaynaklarla birebir aynı olduğunu doğrula.
