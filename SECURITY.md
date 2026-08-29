# Güvenlik ve veri gizliliği

Bu depo gerçek müşteri, personel, banka hareketi veya şirket içi kod verisi
içermemelidir.

- Gerçek girdileri `local_data/` veya `inputs/` altında saklayın.
- Üretilen dosyaları `outputs/` altında saklayın.
- Şirkete özel bölge ve çıktı profillerini `config/local/` altında tutun.
- Testlerde yalnız açıkça yapay isimler ve numaralar kullanın.
- Commit öncesinde `python scripts/check_public_data.py` komutunu çalıştırın.

Yanlışlıkla hassas veri commit edilirse yalnız dosyayı silmek yeterli değildir;
Git geçmişi de temizlenmeli ve ilgili erişim bilgileri gerekiyorsa yenilenmelidir.
