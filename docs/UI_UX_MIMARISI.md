# Çarpan UI/UX mimarisi

Karar tarihi: 12 Eylül 2026. Amaç, Çarpan'ı yalnızca Excel çıktısı üreten bir
masaüstü uygulamasından; günlük finans operasyonunun anlaşılır, güven veren ve
hızlı çalışma alanına dönüştürmektir.

## Tasarım ilkesi

Kullanıcı her ekranda şu üç sorunun yanıtını ilk bakışta görmelidir:

1. Şu an ne durumda?
2. Benden hangi aksiyon bekleniyor?
3. Bu aksiyon neyi değiştirecek?

Arayüz teknik günlük veya ham finansal veri duvarı olmaz. Özet önde, ayrıntı
isteyene bir adım sonra açılır. Hiçbir görsel kolaylık otomatik Netsis/Psoft
aktarımına, otomatik kabul kararına veya onaylı Excel şablonlarına müdahale
etmez.

## Referanslardan alınan kararlar

- QuickBooks'taki iş merkezi yaklaşımı: sol menü yalnız iş merkezlerini taşır;
  ana alan ilgili işin özetini, bekleyen aksiyonlarını ve hızlı başlangıcını
  gösterir.
- SAP Fiori'deki sayfa kalıpları: operasyon listelerinde arama/filtre tek bir
  üst araç çubuğunda kalır; yoğun veride tablo, tek bir iş nesnesinde ayrıntı
  paneli kullanılır.
- Power BI yaklaşımı: yönetici özeti tek ekranda bir hikâye anlatır. En önemli
  metrikler üstte, ayrıntı aşağıda olur; gereksiz grafik, halka ve sayaçlar
  kullanılmaz.
- Erişilebilir tasarım sistemleri: renk tek başına anlam taşımaz. Durum; etiket,
  kısa metin, simge ve klavye ile de anlaşılır olur.

## Ortak uygulama kabuğu — UI-1

- Sol menü üç grupta kalır: Operasyonlar, Kontrol ve Yönetim. Aktif ekran,
  turuncu çizgi ve açık zeminle net görünür; menü daraltılabilir.
- Üst çubukta firma/çalışma alanı, genel arama, bildirim merkezi ve kullanıcı
  menüsü bulunur. Günlük işin birincil başlatma eylemi ekran başlığının sağında
  yalnız bir adet ana düğme olarak görünür.
- Ortak durum dili: Hazır (mavi), Tamamlandı (yeşil), Kontrol gerekli (turuncu),
  Hata/ret (kırmızı), Bilgi (gri). Metin etiketleri renk olmadan da anlamı taşır.
- Ortak kart, tablo, filtre çubuğu, boş durum, hata açıklaması ve yükleniyor
  bileşenleri tek kaynakta tanımlanır. Ekranlar kendi kart görünümünü üretmez.

## Ana operasyon ekranları — UI-2

MANİM Aktarma, FOM Rapor Düzenleme ve Banka Mutabakatı aynı iskeleti kullanır:

1. Girdi seçimi: neyin yüklendiği, türü ve hazırlık durumu.
2. Kontrol/plan: bulunan bölgeler, banka sayısı, toplamlar ve uyarılar.
3. İşlem: yalnız o ekrana ait açık, tek bir birincil eylem.
4. Sonuç: üretilen dosyalar, aktarım öncesi/sonrası özet, dikkat gerektirenler
   ve bir sonraki güvenli adım.

MANİM'de bölge/banka dağılımı ve simülasyon; FOM'da tanınan raporlar ve şablon
doğrulaması; mutabakatta ise tutar farkı ile nokta atışı kayıtlar aynı yerde
ama kendi dilinde gösterilir. İlerlemenin durumu başlık altında sabit kalır;
ayrıntılı günlük ikinci kademe panelden açılır.

## Operasyon Merkezi ve iş listeleri — UI-3

- Operasyon Merkezi tek ekranda günlük durumu anlatır: bugün/son 7 gün,
  bekleyen incelemeler, simülasyon farkı, ERP kalite sinyali ve mutabakat
  kontrolü.
- Kartların her biri ilgili filtrelenmiş listeye açılır; kart sayısı sınırlı
  tutulur. Kart sadece sayıyı değil, kullanıcı için bir sonraki adımı da yazar.
- İnceleme, geçmiş işlem ve ret listelerinde sabit araç çubuğu; tarih, bölge,
  banka, durum ve arama filtreleri bulunur. Satır seçilince sağ ayrıntı paneli
  açılır; kullanıcı ana listeden kopmaz.
- Sayfalama veya kontrollü artan yükleme, binlerce satırda akıcılığı korur.
  Sütun seçimi, sıralama ve filtre tercihleri kullanıcı/firma kapsamında
  saklanacak ayrı bir UI tercihi katmanında ele alınır.

## Son kalite turu — UI-4

- 100%, 125% ve 150% Windows ölçeğinde; klavye odağı, ekran okuyucu etiketleri,
  boş durum, hata/ret metinleri ve uzun Türkçe içerikler kontrol edilir.
- Her ana ekran gerçek günlük akışıyla izlenir: kullanıcı hangi aşamada
  beklediğini, neyin değişmeyeceğini ve sonucu nasıl kontrol edeceğini yardım
  almadan anlayabilmelidir.
- Gözleme göre metin, sıra ve boşluklar düzeltilir. Bu turda hesaplama kuralı
  veya onaylı Excel şablonu değişikliği yapılmaz.

## Teslim sırası

1. UI-1: ortak uygulama kabuğu ve tasarım sistemi. **Tamamlandı:**
   daraltılabilir gezinme, ekran bağlamını gösteren üst çalışma alanı başlığı
   ve ortak durum yüzeyi eklendi.
2. UI-2A: MANİM çalışma yüzeyi. **Tamamlandı:**
   aktarım ekranında girdi/plan/işlem/sonuç akışı görünür hâle getirildi;
   çıktı özeti dört metrikle (kaynak hareketi, Netsis satırı, inceleme ve
   bekleyen bakiye) işlem sonucunda doğrudan gösteriliyor. Teknik günlük ayrı
   sekmede tutuluyor; mevcut işlem ve şablon kuralları değiştirilmedi.
3. UI-2B: FOM ve Banka Mutabakatı çalışma yüzeyleri. **Tamamlandı:**
   FOM işlem alanına çıktı sayısı, kontrol bekleyen kayıt ve çalışma tipi;
   Banka Mutabakatı'na eşleşen, yalnız banka, yalnız Netsis ve toplam fark
   özetleri eklendi. Ayrıntılı günlük ve nokta atışı rapor kartları korunuyor.
4. UI-3: Operasyon Merkezi, geçmiş ve inceleme listeleri. **İlk düzenleme:**
   geçmiş, dikkat ve kurtarma tablolarında satır seçimi, sıralama ve dönüşümlü
   satır görünümü ortaklaştırıldı; Geçmiş İşlemler ekranında seçilen kaydın
   güvenli sonraki adımı liste altında görünür hâle getirildi. Sağ ayrıntı
   paneli listeye eklendi; seçilen işlemin durumu, özeti, çıktı dosyaları ve
   güvenli sonraki adımı aynı ekranda gösteriliyor. Operasyon Merkezi özet
   kartlarına dikkat listesine giden görünür "İncelemeye git" aksiyonu eklendi.
5. UI-4: erişilebilirlik, ölçek, performans ve gerçek kullanım kabulü.

Her teslim; ekran kodu, ilgili ekran testi, %100/%125/%150 görsel kontrolü ve
şablon bütünlüğü doğrulamasıyla kapanır. VPS, SQL, canlı banka bağlantısı ve
web paneli bu yerel UI aşamalarının ön koşulu değildir.

## Başvuru kaynakları

- Intuit QuickBooks: dashboard ve iş merkezi yaklaşımı.
- SAP Fiori: dinamik sayfa, worklist, liste/ayrıntı ve eylem yerleşimi.
- Microsoft Power BI: tek ekranda karar özeti ve metrik hiyerarşisi.
- Atlassian Design System: erişilebilir, tutarlı bileşen kullanımı.
