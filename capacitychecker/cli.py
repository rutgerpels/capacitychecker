from __future__ import annotations

import argparse
import sys

from . import __version__
from .cache import CacheError, CacheStore
from .matrix import build_matrix
from .providers import AzureCliProvider, ProviderError
from .renderers import render_csv, render_json, render_table, write_output


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.version:
        write_output(__version__)
        return 0

    if args.command != "check":
        parser.print_help()
        return 2

    try:
        cache_store = CacheStore()
        if args.clear_cache:
            removed = cache_store.clear()
            write_output(f"Cleared {removed} cache entr{'y' if removed == 1 else 'ies'} from {cache_store.path()}.")
            return 0
        if args.cache_info:
            write_output(_render_cache_info(cache_store))
            return 0

        skus = _collect_values(args.sku, args.skus, "sku")
        regions = _collect_values(args.region, args.regions, "region")
        zones = _collect_zones(args.zones)
        spot_desired_count = _collect_positive_int(args.spot_desired_count, "spot-desired-count")
        provider = _build_provider(args, cache_store)
        rows = build_matrix(
            provider,
            skus,
            regions,
            zones,
            include_spot_score=args.include_spot_score,
            spot_desired_count=spot_desired_count,
        )
        write_output(_render(args.output, rows, args.subscription))
        return 0
    except (CacheError, ProviderError, ValueError) as exc:
        print(f"capacitychecker: error: {exc}", file=sys.stderr)
        return 1


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="capacitychecker", description="Check Azure VM SKU capacity signals across regions.")
    parser.add_argument("--version", action="store_true", help="Print the tool version and exit.")
    subparsers = parser.add_subparsers(dest="command")

    check = subparsers.add_parser("check", help="Build a SKU x region capacity matrix.")
    check.add_argument("--sku", action="append", default=[], help="Single SKU to check. Can be specified multiple times.")
    check.add_argument("--skus", help="Comma-separated list of SKUs to check.")
    check.add_argument("--region", action="append", default=[], help="Single Azure region to check. Can be specified multiple times.")
    check.add_argument("--regions", help="Comma-separated list of Azure regions to check.")
    check.add_argument("--zones", help="Comma-separated availability zones to evaluate, such as 1,2,3.")
    check.add_argument("--subscription", help="Azure subscription id or name to pass to Azure CLI.")
    check.add_argument("--output", choices=["table", "json", "csv"], default="table", help="Output format.")
    check.add_argument("--no-cache", action="store_true", help="Bypass persistent cache reads and writes for this run.")
    check.add_argument("--clear-cache", action="store_true", help="Clear persistent cache entries and exit.")
    check.add_argument("--cache-info", action="store_true", help="Show persistent cache location and entry summary, then exit.")
    check.add_argument(
        "--include-spot-score",
        action="store_true",
        help="Fetch Microsoft Spot Placement Score guidance for Spot placement likelihood.",
    )
    check.add_argument(
        "--spot-desired-count",
        type=int,
        default=1,
        help="Desired Spot VM instance count to use with --include-spot-score. Default: 1.",
    )
    check.add_argument(
        "--enable-live-sku-metadata",
        dest="enable_live_sku_metadata",
        action="store_true",
        help="Fetch offered/restricted signals from Azure Resource SKUs metadata. Enabled by default.",
    )
    check.add_argument(
        "--skip-live-sku-metadata",
        dest="enable_live_sku_metadata",
        action="store_false",
        help="Skip Azure Resource SKUs metadata and use quota/headroom signals only.",
    )
    check.set_defaults(enable_live_sku_metadata=True)
    return parser


def _build_provider(args: argparse.Namespace, cache_store: CacheStore) -> AzureCliProvider:
    return AzureCliProvider(
        subscription=args.subscription,
        enable_live_sku_metadata=args.enable_live_sku_metadata,
        cache_store=cache_store,
        cache_enabled=not args.no_cache,
    )


def _collect_values(single_values: list[str], comma_values: str | None, name: str) -> list[str]:
    values: list[str] = []
    values.extend(single_values or [])
    if comma_values:
        values.extend(comma_values.split(","))

    cleaned = [value.strip() for value in values if value and value.strip()]
    if not cleaned:
        raise ValueError(f"At least one --{name} or --{name}s value is required.")
    return list(dict.fromkeys(cleaned))


def _collect_zones(zones: str | None) -> list[str | None]:
    if not zones:
        return [None]
    cleaned = [zone.strip() for zone in zones.split(",") if zone.strip()]
    if not cleaned:
        raise ValueError("--zones was provided but no zone values were found.")
    return cleaned


def _collect_positive_int(value: int, name: str) -> int:
    if value < 1:
        raise ValueError(f"--{name} must be greater than zero.")
    return value


def _render_cache_info(cache_store: CacheStore) -> str:
    entries = cache_store.describe()
    lines = [f"Cache directory: {cache_store.path()}", f"Entries: {len(entries)}"]
    if not entries:
        return "\n".join(lines)

    lines.append("Namespace  Status   Key")
    lines.append("---------  -------  ---")
    for entry in entries:
        status = "expired" if entry.expired else "fresh"
        lines.append(f"{entry.namespace.ljust(9)}  {status.ljust(7)}  {entry.cache_key[:12]}")
    return "\n".join(lines)


def _render(output: str, rows: list, subscription: str | None) -> str:
    if output == "json":
        return render_json(rows, subscription=subscription)
    if output == "csv":
        return render_csv(rows)
    return render_table(rows)
