from datetime import datetime

import pytest

from app.core.movement_classifier import MovementClassifier, MovementRoute
from app.models.records import ManimRecord


def _record(status: str, amount: float = 100, description: str = "TEST") -> ManimRecord:
    return ManimRecord(
        banka="Garanti",
        sube="TEST",
        islem_tarihi=datetime(2026, 9, 5),
        aciklama=description,
        tutar=amount,
        dekont_durumu=status,
        karsi_hesap_adi="",
        karsi_hesap_kodu="",
        kaynak_dosya="test.xlsx",
        kaynak_satir=2,
    )


@pytest.mark.parametrize(
    ("record", "route", "code"),
    [
        (_record("Ödeme Onaylandı"), MovementRoute.ODEME_ONAYLANDI, "PAYMENT_APPROVED"),
        (_record("Ödeme Onaylandı", -100), MovementRoute.REVIEW, "NEGATIVE_PAYMENT_APPROVAL"),
        (_record("Kural Çalıştı"), MovementRoute.KURAL_CALISTI, "RULE_TRIGGERED"),
        (_record("Referanslı"), MovementRoute.REFERANSLI, "REFERENCE"),
        (_record("Referanslı", description="ROTA104 YATAN PARA"), MovementRoute.REVIEW, "AMBIGUOUS_STAFF_DEPOSIT"),
        (_record("Aktarıldı"), MovementRoute.HAVALE, "TRANSFER"),
    ],
)
def test_movement_classifier_routes_records(record, route, code):
    result = MovementClassifier().classify(record)
    assert result.route == route
    assert result.code == code
