# 2B — Ekip görevleri ve onay iş akışı

12 Eylül 2026. Yerel MANİM inceleme grupları üzerinden uygulanmıştır.

Son doğrulama: 101 ilgili test geçti. Görev/yetki testleriyle birlikte mevcut
MANİM, FOM, geçmiş ve simülasyon testleri çalıştırıldı. Qt filtre API'sine ait
dört mevcut kullanımdan kaldırma uyarısı var. 760 ve 1100 piksel içerik
genişliklerinde görev ekranı sentetik verilerle görsel olarak kontrol edildi.

## Kullanım

Operasyon Merkezi'nin en üstündeki Ekip görevleri ve onaylar alanından:

1. Açık görevi üzerinize alın veya yönetici olarak aktif ekip üyesine atayın.
2. İncelemeye başlayın. Birleşik havalelerin tüm kaynak hareketleri, toplamı ve nedenleri ayrıntıda görülebilir.
3. Karar ve gerekçe girerek onaya gönderin.
4. Yönetici/onay sorumlusu onaylar veya gerekçeyle düzeltmeye iade eder.
5. İade edilen görevi sorumlusu yeniden inceler. Tamamlanmış görevleri yönetici gerekçeyle yeniden açabilir.

Atamada 1/3/7 gün hedefi veya hedefsiz çalışma seçilebilir. Benim görevlerim, atanmamış, geciken, durum ve metin filtreleri vardır. Görev onayı Excel üretmez; dış Netsis/Psoft kabul kaydı ayrı kalır.

## Rol sözleşmesi

| Rol | Görev erişimi | İşlem |
| --- | --- | --- |
| Yönetici | Firma görevleri | Atama, inceleme, onay/iade, yeniden açma, görev bölgeleri yönetimi |
| Operatör | Yetkili görev bölgeleri | Sahipsiz işi alma, kendisine atanmış işi inceleme ve onaya gönderme |
| Onay sorumlusu | Yetkili görev bölgeleri | Kendi işini inceleme; başka kişinin gönderdiğini onaylama/iade |
| Denetçi | Yetkili görev bölgeleri | Salt okunur görev ve karar geçmişi |

Tek kullanıcı yönetici kendi kararını onaylayabilir; diyalog bunu açıkça belirtir ve denetim kaydında self_approval tutulur. Onay sorumlusuna aynı istisna verilmez.

Ekip ve Yetkiler > Görev bölgeleri yalnız inceleme görevlerine uygulanır. `*` tüm bölgeler; aksi halde virgülle ayrılmış bölge isimleri. Karma bölge grubunun tüm bölgeleri yetkide değilse grubun tamamı gizlenir ve atama/karar reddedilir. Bu ayar genel rapor modüllerine satır bazında erişim kontrolü sağladığı iddiasını taşımaz. Genel rapor yetkileri mevcut firma/modül sözleşmesindedir.

## Teknik sınırlar ve doğrulama

- Kimlik/yetki kararları identity.py içindedir. Hassas görev işlemlerinde kullanıcının aktif firma üyeliği ve rolü yeniden okunur.
- Identity migration 2 görev bölgesi tablosunu ekler. Görev akışı, eski queue grup/üye tablolarını yeniden oluşturmadan ek state ve audit tabloları kullanır. Önceki çözülmüş gruplar korunur.
- review_workflow.py yerel uygulama servisidir. Arayüz doğrudan kuyruk geçişi yapmaz. Eski kuyruk geçişleri yeni iş akışı kurulduğunda bypass sağlayamaz.
- Görev durumu, sürümü, sorumlusu ve denetim olayı aynı SQLite işlemi içinde güncellenir. Eski sürüm kararları reddedilir. Atayan ve atanan ayrı alanlardır.
- Denetim tablosu güncelleme/silme tetikleyicileriyle korunur ve firma başına hash zinciriyle doğrulanır. Bu, veritabanı dosyasının işletim sistemi sahibine karşı mutlak değiştirilemezlik veya harici imzalı kayıt sistemi değildir.
- Karar geçmişi önceki kuyruk olaylarını da gösterir. Kaynak üye kimlikleri/şablonlar değiştirilmez.
- tests/test_review_workflow.py: akış, rol, canlı erişim iptali, bölge, firma, atama kimliği, eşzamanlı sahiplenme, atomik geri alma, eski kayıt uyumu, tek kullanıcı yönetici onayı.
- tests/test_review_board.py: gerçek görev servisiyle filtre/eylem uygunluğu, erişim kaldırma sonrası liste temizliği, 760/1100 piksel içerik genişliğinde ekran kontrolü.

Merkezi SQL/API görevi paylaşımı bu pakette etkin değildir. Arayüzün bağımlı olduğu uygulama servisi, daha sonra merkezi taşıyıcıya uyarlanacak sınırı sağlar. Farklı bilgisayarlarda eşzamanlı ekip kullanımı için merkezi servis gerekir; bu teslim yerel şirket çalışma alanında çalışır.
