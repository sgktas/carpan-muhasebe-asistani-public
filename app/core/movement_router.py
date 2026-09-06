from __future__ import annotations

from dataclasses import dataclass

from app.core.movement_classifier import MovementClassifier, MovementRoute
from app.core.region_config import RegionConfig
from app.core.virman_detector import VirmanDetector
from app.models.records import ManimRecord, VirmanRecord


@dataclass(frozen=True)
class MovementDecision:
    """Bir MANİM hareketi için tek ve denetlenebilir yönlendirme kararı."""

    route: MovementRoute
    code: str
    reason: str = ""
    candidate: bool = False
    virman_record: VirmanRecord | None = None


class MovementRouter:
    """Dekont durumu ve banka hareketi kurallarını tek öncelik sırasına bağlar."""

    def __init__(self, region_config: RegionConfig):
        self.classifier = MovementClassifier()
        self.virman_detector = VirmanDetector(region_config)

    def route(self, record: ManimRecord, source_region: str) -> MovementDecision:
        classification = self.classifier.classify(record)
        if classification.route != MovementRoute.REFERANSLI:
            return MovementDecision(
                route=classification.route,
                code=classification.code,
                reason=classification.reason,
            )
        return self.route_reference(record, source_region)

    def route_reference(
        self,
        record: ManimRecord,
        source_region: str,
    ) -> MovementDecision:
        """Referanslı bir hareketi aynı-banka virmanı veya normal kayıt yapar."""
        detection = self.virman_detector.detect(record, source_region)
        if detection.record is not None:
            return MovementDecision(
                route=MovementRoute.SAME_BANK_VIRMAN,
                code="SAME_BANK_INTERNAL_TRANSFER",
                virman_record=detection.record,
                candidate=True,
            )
        if detection.candidate:
            return MovementDecision(
                route=MovementRoute.REFERANSLI,
                code="VIRMAN_REVIEW_REQUIRED",
                reason=detection.reason,
                candidate=True,
            )
        return MovementDecision(
            route=MovementRoute.REFERANSLI,
            code="REFERENCE",
        )
