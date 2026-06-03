from __future__ import annotations

from typing import Any

from .models import CapacityRow, QuotaHeadroom, utc_now_iso
from .providers import CapacityProvider


def build_matrix(provider: CapacityProvider, skus: list[str], regions: list[str], zones: list[str | None]) -> list[CapacityRow]:
    rows: list[CapacityRow] = []
    checked_at = utc_now_iso()

    for region in regions:
        usage = provider.list_usage(region)
        for sku in skus:
            sku_records = provider.list_skus(region, sku)
            sku_metadata_available = sku_records is not None
            sku_record = _find_sku_record(sku_records or [], sku, region)
            for zone in zones:
                rows.append(_build_row(provider.source_name, sku, region, zone, sku_metadata_available, sku_record, usage, checked_at))

    return rows


def _build_row(
    source_name: str,
    sku: str,
    region: str,
    zone: str | None,
    sku_metadata_available: bool,
    sku_record: dict[str, Any] | None,
    usage: list[dict[str, Any]],
    checked_at: str,
) -> CapacityRow:
    notes: list[str] = []
    offered = _is_offered(sku_metadata_available, sku_record, region, zone)
    restricted = _is_restricted(sku_record, region, zone) if offered else None
    quota = _quota_headroom(sku, usage)

    if offered is None:
        if quota and quota.value is not None and quota.value <= 0:
            allocatable = "likely_no"
            confidence = "medium"
            notes.append("Live SKU metadata was skipped; quota headroom is zero or below.")
        else:
            allocatable = "unknown"
            confidence = "low"
            notes.append("Live SKU metadata is unavailable in MVP live mode; use fixture data or opt in to live SKU metadata for offered/restricted signals.")
    elif not offered:
        allocatable = "no"
        confidence = "high"
        notes.append("SKU is not offered for this region/zone based on ResourceSkus metadata.")
    elif restricted is True:
        allocatable = "likely_no"
        confidence = "medium" if quota else "low"
        notes.append("Azure metadata reports a restriction for this SKU/region/zone.")
    elif quota and quota.value is not None and quota.value <= 0:
        allocatable = "likely_no"
        confidence = "high"
        notes.append("Subscription quota headroom is zero or below.")
    elif quota and quota.value is not None and quota.value > 0:
        allocatable = "likely_yes"
        confidence = "high"
    else:
        allocatable = "unknown"
        confidence = "medium" if restricted is False else "low"
        notes.append("Quota headroom is unavailable; recommendation is inconclusive.")

    return CapacityRow(
        sku=sku,
        region=region,
        zone=zone,
        offered=offered,
        capacity_restricted=restricted,
        spot_pressure="unknown",
        quota_headroom=quota,
        allocatable=allocatable,
        confidence=confidence,
        sources=[source_name, "ResourceSkus" if sku_metadata_available else "Usage/Quota only", "Usage/Quota"],
        freshness_seconds=0,
        checked_at=checked_at,
        notes=notes,
    )


def _find_sku_record(records: list[dict[str, Any]], sku: str, region: str) -> dict[str, Any] | None:
    for record in records:
        if str(record.get("name", "")).casefold() != sku.casefold():
            continue
        locations = [str(location).casefold() for location in record.get("locations", [])]
        if not locations or region.casefold() in locations:
            return record
    return None


def _is_offered(sku_metadata_available: bool, record: dict[str, Any] | None, region: str, zone: str | None) -> bool | None:
    if not sku_metadata_available:
        return None
    if record is None:
        return False
    if zone is None:
        return True

    for location_info in record.get("locationInfo", []) or []:
        if str(location_info.get("location", "")).casefold() != region.casefold():
            continue
        zones = [str(item) for item in location_info.get("zones", []) or []]
        return zone in zones
    return False


def _is_restricted(record: dict[str, Any] | None, region: str, zone: str | None) -> bool:
    if record is None:
        return False

    for restriction in record.get("restrictions", []) or []:
        if _restriction_applies(restriction, region, zone):
            return True
    return False


def _restriction_applies(restriction: dict[str, Any], region: str, zone: str | None) -> bool:
    info = restriction.get("restrictionInfo") or {}
    locations = [str(item).casefold() for item in info.get("locations", []) or []]
    zones = [str(item) for item in info.get("zones", []) or []]
    values = [str(item) for item in restriction.get("values", []) or []]

    location_applies = not locations or region.casefold() in locations
    if not location_applies:
        return False

    if zone is None:
        return True

    if zones:
        return zone in zones
    if values and str(restriction.get("type", "")).casefold() == "zone":
        return zone in values
    return True


def _quota_headroom(sku: str, usage: list[dict[str, Any]]) -> QuotaHeadroom | None:
    if not usage:
        return None

    family_hint = _sku_family_hint(sku)
    candidates = sorted(usage, key=lambda item: _usage_score(item, family_hint), reverse=True)
    for candidate in candidates:
        limit = _parse_int(candidate.get("limit"))
        current = _parse_int(candidate.get("currentValue"))
        if limit is None or current is None:
            continue
        if limit < 0:
            return QuotaHeadroom(value=None, unit="vCPU", limit=limit, current=current, source_name=_usage_name(candidate))
        return QuotaHeadroom(value=max(limit - current, 0), unit="vCPU", limit=limit, current=current, source_name=_usage_name(candidate))
    return None


def _usage_score(item: dict[str, Any], family_hint: str) -> int:
    usage_name = _usage_name(item).casefold().replace(" ", "")
    if family_hint and family_hint in usage_name:
        return 100
    if "standard" in usage_name and "family" in usage_name and family_hint[:8] in usage_name:
        return 50
    if "totalregionalvcpus" in usage_name or "total regional vcpus" in usage_name:
        return 10
    if "cores" in usage_name or "vcpus" in usage_name:
        return 1
    return 0


def _usage_name(item: dict[str, Any]) -> str:
    name = item.get("name")
    if isinstance(name, dict):
        return str(name.get("value") or name.get("localizedValue") or "")
    return str(name or "")


def _parse_int(value: Any) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return None
    return None


def _sku_family_hint(sku: str) -> str:
    parts = sku.split("_", 1)
    if len(parts) != 2:
        return ""
    family = parts[1]
    family = "".join(character for character in family if not character.isdigit() and character != "_")
    return f"standard{family}family".casefold()
