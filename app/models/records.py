from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class ManimRecord:
    banka: str
    sube: str
    islem_tarihi: datetime | None
    aciklama: str
    tutar: float
    dekont_durumu: str
    karsi_hesap_adi: str
    karsi_hesap_kodu: str
    kaynak_dosya: str
    kaynak_satir: int
    ham_veri: dict = field(default_factory=dict)


@dataclass(frozen=True)
class TahsilatRecord:
    musteri_kodu: str
    musteri_ismi: str
    belge_tarihi: datetime | None
    tutar: float


@dataclass(frozen=True)
class CustomerRecord:
    cari_kodu: str
    unvan: str
    vergi_no: str
    sube: str
    tabela_adi: str = ""


@dataclass(frozen=True)
class NetsisRecord:
    islem_tarihi: datetime | None
    cari_kodu: str
    tutar: float
    aciklama: str
    banka: str
    bolge: str
    kaynak: str
    banka_hesap_kodu: str = ""


@dataclass(frozen=True)
class BankStatementRecord:
    """Banka ekstresindeki tek bir satır (Modül 03 - Banka Mutabakatı).

    ``bakiye``, o satırdan sonraki kümülatif (running) hesap bakiyesidir.
    """

    tarih: datetime | None
    aciklama: str
    tutar: float
    bakiye: float | None
    kaynak_dosya: str
    kaynak_satir: int


@dataclass(frozen=True)
class NetsisReportRecord:
    """Netsis'ten alınan ay sonu raporundaki tek bir satır (Modül 03).

    ``bakiye``, o satırdan sonraki kümülatif (running) hesap bakiyesidir.
    """

    tarih: datetime | None
    aciklama: str
    tutar: float
    bakiye: float | None
    kaynak_dosya: str
    kaynak_satir: int
