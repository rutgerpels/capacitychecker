from __future__ import annotations

import csv
import json
import sys
from io import StringIO

from .models import CapacityRow, utc_now_iso


def render_table(rows: list[CapacityRow]) -> str:
    headers = ["SKU", "Region", "Zone", "Offered", "Restricted", "Spot", "Quota", "Allocatable", "Confidence"]
    body = [
        [
            row.sku,
            row.region,
            row.zone or "-",
            _maybe_yes_no(row.offered),
            _maybe_yes_no(row.capacity_restricted),
            row.spot_placement_guidance,
            _quota(row),
            row.allocatable,
            row.confidence,
        ]
        for row in rows
    ]
    widths = [len(header) for header in headers]
    for record in body:
        for index, value in enumerate(record):
            widths[index] = max(widths[index], len(value))

    lines = [_format_table_line(headers, widths), _format_table_line(["-" * width for width in widths], widths)]
    lines.extend(_format_table_line(record, widths) for record in body)
    return "\n".join(lines)


def render_json(rows: list[CapacityRow], subscription: str | None = None) -> str:
    payload = {
        "timestamp": utc_now_iso(),
        "subscription": subscription,
        "results": [row.to_dict() for row in rows],
    }
    return json.dumps(payload, indent=2, sort_keys=True)


def render_csv(rows: list[CapacityRow]) -> str:
    output = StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=[
            "SKU",
            "Region",
            "Zone",
            "Offered",
            "Capacity_Restricted",
            "Spot_Pressure",
            "Spot_Placement_Score",
            "Spot_Placement_Guidance",
            "Spot_Quota_Available",
            "Quota_Headroom_Value",
            "Quota_Headroom_Unit",
            "Quota_Limit",
            "Quota_Current",
            "Allocatable",
            "Confidence",
            "Freshness_Seconds",
            "Checked_At",
            "Notes",
        ],
        lineterminator="\n",
    )
    writer.writeheader()
    for row in rows:
        quota = row.quota_headroom
        writer.writerow(
            {
                "SKU": row.sku,
                "Region": row.region,
                "Zone": row.zone or "",
                "Offered": "" if row.offered is None else str(row.offered).lower(),
                "Capacity_Restricted": "" if row.capacity_restricted is None else str(row.capacity_restricted).lower(),
                "Spot_Pressure": row.spot_pressure,
                "Spot_Placement_Score": row.spot_placement_score or "",
                "Spot_Placement_Guidance": row.spot_placement_guidance,
                "Spot_Quota_Available": "" if row.spot_quota_available is None else str(row.spot_quota_available).lower(),
                "Quota_Headroom_Value": "" if quota is None or quota.value is None else quota.value,
                "Quota_Headroom_Unit": "" if quota is None else quota.unit,
                "Quota_Limit": "" if quota is None or quota.limit is None else quota.limit,
                "Quota_Current": "" if quota is None or quota.current is None else quota.current,
                "Allocatable": row.allocatable,
                "Confidence": row.confidence,
                "Freshness_Seconds": row.freshness_seconds,
                "Checked_At": row.checked_at,
                "Notes": " | ".join(row.notes),
            }
        )
    return output.getvalue()


def write_output(text: str) -> None:
    sys.stdout.write(text)
    if not text.endswith("\n"):
        sys.stdout.write("\n")


def _format_table_line(values: list[str], widths: list[int]) -> str:
    return "  ".join(value.ljust(widths[index]) for index, value in enumerate(values))


def _yes_no(value: bool) -> str:
    return "yes" if value else "no"


def _maybe_yes_no(value: bool | None) -> str:
    if value is None:
        return "unknown"
    return _yes_no(value)


def _quota(row: CapacityRow) -> str:
    quota = row.quota_headroom
    if quota is None:
        return "unknown"
    if quota.value is None:
        return "unlimited"
    return f"{quota.value} {quota.unit}"
