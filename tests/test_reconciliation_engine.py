from datetime import datetime

from app.core.reconciliation_engine import ReconciliationEngine
from app.models.records import BankStatementRecord, NetsisReportRecord


def _bank(tarih, tutar, bakiye, satir=1):
    return BankStatementRecord(
        tarih=tarih, aciklama="test", tutar=tutar, bakiye=bakiye,
        kaynak_dosya="ekstre.xlsx", kaynak_satir=satir,
    )


def _netsis(tarih, tutar, bakiye, satir=1):
    return NetsisReportRecord(
        tarih=tarih, aciklama="test", tutar=tutar, bakiye=bakiye,
        kaynak_dosya="netsis.xlsx", kaynak_satir=satir,
    )


def test_bakiyeler_tutuyorsa_mutabik():
    bank = [
        _bank(datetime(2026, 7, 1), 1000.0, 1000.0, 1),
        _bank(datetime(2026, 7, 5), -200.0, 800.0, 2),
    ]
    netsis = [
        _netsis(datetime(2026, 7, 1), 1000.0, 1000.0, 1),
        _netsis(datetime(2026, 7, 5), -200.0, 800.0, 2),
    ]
    result = ReconciliationEngine().reconcile(bank, netsis)
    assert result.mutabik is True
    assert result.fark == 0
    assert result.eslesen_sayisi == 2
    assert result.sadece_bankada == []
    assert result.sadece_netposte == []


def test_bolunmus_fis_ayni_gun_ayni_aciklama_toplami_esitse_eslesir():
    # Banka tek satirda 43261.50 yatirmis, Netsis bunu 3 ayri satira bolmus
    # (Modul 01'deki 'Subeliler' kaydiyla ayni gercek dunya durumu).
    aciklama = "FAST8881412-SELİKA-SELİMİYE KARDEŞLER GIDA TURİ-FA"
    bank = [_bank(datetime(2026, 6, 8), 43261.50, 100.0, 1)]
    netsis = [
        _netsis(datetime(2026, 6, 8), 20389.25, 100.0, 1),
        _netsis(datetime(2026, 6, 8), 17763.00, 100.0, 2),
        _netsis(datetime(2026, 6, 8), 5109.25, 100.0, 3),
    ]
    # aciklama alanlarini ayarla (yardimci fonksiyonlar "test" kullaniyor, elle degistiriyoruz)
    bank[0] = bank[0].__class__(**{**bank[0].__dict__, "aciklama": aciklama})
    netsis = [n.__class__(**{**n.__dict__, "aciklama": aciklama}) for n in netsis]

    result = ReconciliationEngine().reconcile(bank, netsis)
    assert result.bolunmus_grup_sayisi == 1
    assert result.sadece_bankada == []
    assert result.sadece_netposte == []
    assert result.eslesen_sayisi == 4  # 1 banka + 3 netsis satiri, hepsi mutabik sayilir


def test_bolunmus_fis_toplam_tutmuyorsa_gercek_fark_olarak_kalir():
    aciklama = "FAST123-TEST MUSTERI"
    bank = [_bank(datetime(2026, 6, 8), 1000.0, 100.0, 1)]
    netsis = [
        _netsis(datetime(2026, 6, 8), 400.0, 100.0, 1),
        _netsis(datetime(2026, 6, 8), 400.0, 100.0, 2),  # toplam 800, 1000 degil
    ]
    bank[0] = bank[0].__class__(**{**bank[0].__dict__, "aciklama": aciklama})
    netsis = [n.__class__(**{**n.__dict__, "aciklama": aciklama}) for n in netsis]

    result = ReconciliationEngine().reconcile(bank, netsis)
    assert result.bolunmus_grup_sayisi == 0
    assert len(result.sadece_bankada) == 1
    assert len(result.sadece_netposte) == 2


def test_bakiye_tutmuyorsa_farkli_kayitlar_listelenir():
    bank = [
        _bank(datetime(2026, 7, 1), 1000.0, 1000.0, 1),
        _bank(datetime(2026, 7, 5), -200.0, 800.0, 2),
        _bank(datetime(2026, 7, 10), -50.0, 750.0, 3),  # sadece bankada
    ]
    netsis = [
        _netsis(datetime(2026, 7, 1), 1000.0, 1000.0, 1),
        _netsis(datetime(2026, 7, 5), -200.0, 800.0, 2),
        _netsis(datetime(2026, 7, 12), -30.0, 770.0, 3),  # sadece netposte
    ]
    result = ReconciliationEngine().reconcile(bank, netsis)
    assert result.mutabik is False
    assert result.fark == 750.0 - 770.0
    assert result.eslesen_sayisi == 2
    assert len(result.sadece_bankada) == 1
    assert result.sadece_bankada[0].tutar == -50.0
    assert len(result.sadece_netposte) == 1
    assert result.sadece_netposte[0].tutar == -30.0


def test_mukerrer_ayni_tarih_tutar_multiset_eslesir():
    # Ayni gunde iki adet ayni tutarli islem var; biri banka fazlasi olmali.
    bank = [
        _bank(datetime(2026, 7, 1), 100.0, 100.0, 1),
        _bank(datetime(2026, 7, 1), 100.0, 200.0, 2),
        _bank(datetime(2026, 7, 1), 100.0, 300.0, 3),
    ]
    netsis = [
        _netsis(datetime(2026, 7, 1), 100.0, 100.0, 1),
        _netsis(datetime(2026, 7, 1), 100.0, 200.0, 2),
    ]
    result = ReconciliationEngine().reconcile(bank, netsis)
    assert result.eslesen_sayisi == 2
    assert len(result.sadece_bankada) == 1
    assert len(result.sadece_netposte) == 0


def test_bos_listeler_bakiyesiz_sonuc_verir():
    result = ReconciliationEngine().reconcile([], [])
    assert result.banka_bakiyesi is None
    assert result.netsis_bakiyesi is None
    assert result.fark is None
    assert result.mutabik is False


def test_manim_yeni_kayit_ustteyse_en_guncel_bakiye_tarihten_bulunur():
    bank = [
        _bank(datetime(2026, 9, 3, 22, 21), 100.0, 174025.42, 2),
        _bank(datetime(2026, 9, 3, 6, 23), 200.0, 8880278.72, 3),
    ]
    netsis = [
        _netsis(datetime(2026, 9, 3), 200.0, 173925.42, 2),
        _netsis(datetime(2026, 9, 3), 100.0, 174025.42, 3),
    ]

    result = ReconciliationEngine().reconcile(bank, netsis)

    assert result.banka_bakiyesi == 174025.42
    assert result.netsis_bakiyesi == 174025.42
    assert result.fark == 0
    assert result.mutabik is True
