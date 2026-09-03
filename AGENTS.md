# Kalıcı kullanıcı talimatı: orijinal çıktı şablonlarını koru

Kullanıcı açıkça istedi: **Netsis şablonunu kesinlikle bozma; yalnızca verilen
ve onaylanan orijinal şablonları kullan.** Bu kural her revize ve paket için geçerlidir.

- Normal havale `templates/local/netsis_template.xls` dosyasını kullanır.
  Bu, kullanıcının verdiği `NETSİS AKTARMA.xls` dosyasının birebir kopyasıdır.
- Toplu havale ve FOM çıktılarında da mevcut onaylı yerel şablonları koru.
- Başlıkları, sütun sırasını, sayfa adını, sütun genişliklerini ve mevcut
  biçimlendirmeyi değiştirme. Tutar sütunlarının binlik ayraçlı, iki ondalıklı
  sayısal biçimini yeni veri satırlarında da koru.
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
