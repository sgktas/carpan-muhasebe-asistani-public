# Entegrasyon mimarisi

Çarpan’ın entegrasyonları üç sınırla çalışır:

1. **Ürün kaydı:** Her bağlantı `app/integrations/registry.py` içinde kimlik,
   kabiliyet, taşıma yöntemi ve veri sınırı ile kaydedilir.
2. **Yerel işleme:** Banka hareketi, müşteri listesi, Excel ve onaylı şablon
   masaüstünde kalır. Merkezi API bunları ilk aşamada kabul etmez.
3. **Adaptör sorumluluğu:** Bir ERP veya banka için dosya okuyucu/yazıcı ya da
   API istemcisi yalnız kendi adaptöründe bulunur; MANİM kararları, müşteri
   eşleştirme ve onaylı Netsis şablonları bu adaptörlere dağıtılmaz.

## Taşıma yöntemleri

- **Yerel onaylı dosya:** Bugünkü Netsis ve Psoft/FOM akışları. Orijinal şablon
  sözleşmesi aynen korunur.
- **Güvenli API:** Gelecekte ERP sağlayıcılarının izinli API’leri. Erişim
  bilgileri işletim sistemi korumalı yerel depoda tutulur; masaüstü PostgreSQL’e
  doğrudan bağlanmaz.
- **Açık bankacılık:** Yalnız uygun lisanslı/izinli sağlayıcı üzerinden eklenir.
  Kullanıcının internet bankacılığı parolası uygulamada saklanmaz.

Yeni bir adaptör eklenmeden önce kabiliyet, veri sınırı, hata/yeniden deneme
davranışı ve denetim kaydı tanımlanmalıdır.
