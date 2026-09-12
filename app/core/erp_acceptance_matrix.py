from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class NetsisAcceptanceRule:
    """Netsis profilinin gerçek aktarım öncesi kabul kuralları."""

    template_format_headers: frozenset[str] = frozenset()
    text_headers: frozenset[str] = frozenset()
    require_date_cells: bool = True
    require_profile_constants: bool = True


@dataclass(frozen=True)
class FomAcceptanceRule:
    """Psoft/FOM entegrasyon dosyasının kabul kuralları."""

    template_format_scope: str = "all"
    text_headers: frozenset[str] = frozenset()


# Bu matris şablon üretmez. Yalnızca kullanıcının onayladığı yerel
# şablondan üretilen dosyanın, ERP'ye gitmeden önce taşıması gereken
# değişmezleri tanımlar.
NETSIS_ACCEPTANCE_MATRIX: dict[str, NetsisAcceptanceRule] = {
    "netsis": NetsisAcceptanceRule(
        template_format_headers=frozenset({
            "Cari Kodu(*)",
            "Tutar",
        }),
        text_headers=frozenset({"Cari Kodu(*)"}),
    ),
    "netsis_toplu": NetsisAcceptanceRule(
        # Onaylı toplu şablonun ikinci satırı boştur. Netsis'in hassas
        # olduğu banka kodu hücresi General kalmalıdır; tutar/tarih biçimi
        # profil ve veri türü kurallarıyla ayrıca denetlenir.
        template_format_headers=frozenset({"Banka Hes.Kodu(*)"}),
        text_headers=frozenset({"Cari Kodu(*)"}),
    ),
    "netsis_virman_toplu": NetsisAcceptanceRule(
        template_format_headers=frozenset({"*"}),
        text_headers=frozenset({"Plas.Kodu"}),
        require_date_cells=False,
    ),
}


FOM_SALES_TEXT_HEADERS = frozenset({
    "MüşteriKodu",
    "FaturaNo",
    "Tarih",
    "KDV",
    "PersonelKodu",
    "ÖdemeTipi",
    "ÜrünKodu",
    "FOC",
    "Tabela Adı",
    "Vergi Dairesi",
    "Vergi No",
    "İlk Matbu No",
    "Fatura Kodu",
    "İrsaliye Kodu",
    "İrsaliye Numarası",
    "İrsaliye Tarihi",
})

FOM_COLLECTION_TEXT_HEADERS = frozenset({
    "MusteriKodu",
    "Musteriİsmi",
    "BelgeNo",
    "BelgeTarihi",
    "TahsilatTipi",
    "TahsilatTuru",
    "SatisElemani",
    "Personel",
    "Rota",
    "MusteriKayitTipi",
    "MusteriTipi",
    "SahiplikTipi",
    "AltTip",
    "FiyatListesi",
    "BANKA",
    "BÖLGE",
})


FOM_ACCEPTANCE_MATRIX: dict[str, FomAcceptanceRule] = {
    "ENT-Muhasebe_Entegrasyon(Satış_Faturaları)": FomAcceptanceRule(
        text_headers=FOM_SALES_TEXT_HEADERS,
    ),
    "ENT-Muhasebe_Entegrasyon(Tahsilatlar)": FomAcceptanceRule(
        text_headers=FOM_COLLECTION_TEXT_HEADERS,
    ),
}


def netsis_acceptance_rule(profile_id: str) -> NetsisAcceptanceRule:
    try:
        return NETSIS_ACCEPTANCE_MATRIX[profile_id]
    except KeyError as error:
        raise ValueError(f"ERP kabul matrisi bulunamadı: {profile_id}") from error


def fom_acceptance_rule(output_basename: str) -> FomAcceptanceRule:
    try:
        return FOM_ACCEPTANCE_MATRIX[output_basename]
    except KeyError as error:
        raise ValueError(f"FOM kabul matrisi bulunamadı: {output_basename}") from error
