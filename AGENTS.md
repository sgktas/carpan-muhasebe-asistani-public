# Kalıcı kullanıcı talimatı: orijinal çıktı şablonlarını koru

Kullanıcı açıkça istedi: **Netsis şablonunu kesinlikle bozma; yalnızca verilen
ve onaylanan orijinal şablonları kullan.** Bu kural her revize ve paket için geçerlidir.

- Normal havale `templates/local/netsis_template.xls` dosyasını kullanır.
  Bu, kullanıcının verdiği `NETSİS AKTARMA.xls` dosyasının birebir kopyasıdır.
- Toplu banka kodlu havale `templates/local/netsis_toplu_template.xlsx`
  dosyasını kullanır. Bu şablon, kullanıcının 8 Eylül 2026 tarihinde Netsis'ten
  doğrudan aldığı `TOPLUGELENHAVALEAKTARIMI.xlsx` dosyasının birebir kopyasıdır.
  Tek sayfası `Sheet1`'dır; 32 başlık, sütun sırası ve çalışma sayfası adı aynen
  korunur. Çıktı `.xlsx` olarak üretilir; `Muh.Ref.Kod(*)` sabiti `G01`'dir.
- Toplu havale ve FOM çıktılarında da mevcut onaylı yerel şablonları koru.
- Psoft/Netsis'e gidecek FOM entegrasyon dosyaları tam olarak
  `ENT-Muhasebe_Entegrasyon(Satış_Faturaları).xls` ve
  `ENT-Muhasebe_Entegrasyon(Tahsilatlar).xls` adlarıyla üretilmelidir.
  Kullanıcı bu adları gerçek aktarımda başarılı olarak doğruladı. Çalışma
  sayfası adı onaylı kaynak şablondan aynen korunmalıdır; dosya veya sayfa
  adını yeniden adlandırma, sadeleştirme ya da dönüştürme yapma.
- Mevcut `templates/local/report_editing/sales_template.xls` ve
  `templates/local/report_editing/collections_template.xls` dosyaları, kullanıcı
  tarafından 8 Eylül 2026 tarihinde çalışan son sürüm olarak tekrar onaylandı.
  Bu iki dosyanın kontrol değeri yalnız bu açık onayla güncellendi.
- FOM entegrasyon çıktısını başarılı saymadan önce `.xls` dosya imzası,
  güvenli dosya/sayfa adı, orijinal şablon başlıkları ve veri satırı sayısı
  çıktı sözleşmesiyle doğrulanmalıdır.
- Başlıkları, sütun sırasını, sayfa adını, sütun genişliklerini ve mevcut
  biçimlendirmeyi değiştirme. Tutar sütunlarının binlik ayraçlı, iki ondalıklı
  sayısal biçimini yeni veri satırlarında da koru.
- Hesaplar arası toplu virman çıktısı
  `templates/local/netsis_virman_toplu_template.xlsx` dosyasını kullanır.
  Bu, kullanıcının 6 Eylül 2026 tarihinde onayladığı şablonun yalnız dolu
  `Sheet1` sayfası bırakılmış güncel sürümüdür. Kaynak banka kodu A, hedef
  banka kodu H, yön değeri 1 ve tutar O sütunundadır. Plas.Kodu U sütununda
  metin olarak `00` görünmelidir; sayısal `0.00` biçimi kullanılmaz.
- MANİM hareket rotaları `app/core/movement_router.py` içindeki tek karar
  katmanından geçmelidir. Aynı banka virmanı dahil rota kararlarını tekrar
  `processing_engine.py` içine dağıtma. Yeni rota eklerken
  `docs/MANIM_YONLENDIRME_MIMARISI.md` sözleşmesini uygula.
- `ProcessingEngine` yalnız MANİM iş akışını koordine eder. Dosya türü tanıma
  `manim_input_classifier.py`, bölge çözümleme `manim_region_resolver.py`,
  birleşik/manüel eşleştirme `manim_resolution.py`, çıktı sıralama ve yazma
  `manim_output_service.py` içinde kalmalıdır. Bu sorumlulukları yeniden ana
  motora taşımadan `docs/MANIM_ISLEME_MIMARISI.md` sınırlarını koru.
- Firma, kullanıcı, parola, rol ve güvenlik denetimi kararları
  `app/core/identity.py` içinde kalmalıdır. Arayüzde rol adına göre dağınık karar
  üretme; `AuthenticatedSession.can()` izinlerini kullan. Kimlik şeması
  değişikliklerinde `schema_migrations` ile geriye uyumlu geçiş ekle.
- Merkezi B2B API yalnız `platform_api/` altında geliştirilir. Masaüstü istemcisi
  PostgreSQL'e doğrudan bağlanamaz; firma kapsamlı merkezi sorgular
  `tenant_transaction()` ve RLS sözleşmesi üzerinden geçmelidir. İlk merkezi
  sürümde banka/Excel/müşteri dosyalarını API'ye taşıma; gerçek gizli değerleri
  `.env`, dokümantasyon, test veya Git içine yazma.
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
