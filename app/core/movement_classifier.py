from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re

from app.models.records import ManimRecord


class MovementRoute(str, Enum):
    HAVALE = "HAVALE"
    ODEME_ONAYLANDI = "ODEME_ONAYLANDI"
    REFERANSLI = "REFERANSLI"
    KURAL_CALISTI = "KURAL_CALISTI"
    REVIEW = "REVIEW"


@dataclass(frozen=True)
class MovementClassification:
    route: MovementRoute
    code: str
    reason: str = ""


class MovementClassifier:
    """MANİM dekont durumunu tek, test edilebilir bir noktada sınıflandırır."""

    def classify(self, record: ManimRecord) -> MovementClassification:
        status = self._normalize(record.dekont_durumu)
        if "ODEME ONAYLANDI" in status:
            if record.tutar < 0:
                return MovementClassification(
                    MovementRoute.REVIEW,
                    "NEGATIVE_PAYMENT_APPROVAL",
                    "Negatif tutarlı kayıt Ödeme Onaylandı olamaz. Bu işlem giden para "
                    "olduğu için Referanslı kayıt olarak kontrol edilmelidir.",
                )
            return MovementClassification(MovementRoute.ODEME_ONAYLANDI, "PAYMENT_APPROVED")

        if "KURAL CALISTI" in status:
            return MovementClassification(MovementRoute.KURAL_CALISTI, "RULE_TRIGGERED")

        if "REFERANSLI" in status:
            if record.tutar > 0 and self.has_staff_route_marker(record.aciklama):
                return MovementClassification(
                    MovementRoute.REVIEW,
                    "AMBIGUOUS_STAFF_DEPOSIT",
                    "Referanslı seçilmiş ancak açıklamada ROTA veya YATAN PARA bilgisi "
                    "tespit edildi. Ödeme Onaylandı olma ihtimaline karşı onay gereklidir.",
                )
            return MovementClassification(MovementRoute.REFERANSLI, "REFERENCE")

        return MovementClassification(MovementRoute.HAVALE, "TRANSFER")

    @staticmethod
    def has_staff_route_marker(description: str) -> bool:
        normalized = MovementClassifier._normalize(description)
        return bool(
            re.search(r"\bROTA[\s.-]*\d{1,4}\b", normalized)
            or "YATAN PARA" in normalized
        )

    @staticmethod
    def _normalize(value: object) -> str:
        translation = str.maketrans("ÇĞİÖŞÜ", "CGIOSU")
        return " ".join(str(value or "").upper().translate(translation).split())
