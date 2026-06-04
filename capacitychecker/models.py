from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class QuotaHeadroom:
    value: int | None
    unit: str = "vCPU"
    limit: int | None = None
    current: int | None = None
    source_name: str | None = None


@dataclass(frozen=True)
class CapacityRow:
    sku: str
    region: str
    zone: str | None
    offered: bool | None
    capacity_restricted: bool | None
    spot_pressure: str
    quota_headroom: QuotaHeadroom | None
    allocatable: str
    confidence: str
    spot_placement_score: str | None = None
    spot_placement_guidance: str = "unknown"
    spot_quota_available: bool | None = None
    sources: list[str] = field(default_factory=list)
    freshness_seconds: int = 0
    checked_at: str = field(default_factory=utc_now_iso)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        if self.quota_headroom is None:
            result["quota_headroom"] = None
        result["allocatable_confidence"] = self.confidence
        result["data_source"] = ", ".join(self.sources)
        return result
