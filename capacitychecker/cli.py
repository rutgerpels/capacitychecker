from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .matrix import build_matrix
from .providers import AzureCliProvider, FixtureProvider, ProviderError
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
        skus = _collect_values(args.sku, args.skus, "sku")
        regions = _collect_values(args.region, args.regions, "region")
        zones = _collect_zones(args.zones)
        provider = _build_provider(args)
        rows = build_matrix(provider, skus, regions, zones)
        write_output(_render(args.output, rows, args.subscription))
        return 0
    except (ProviderError, ValueError) as exc:
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
    check.add_argument("--mock-skus-file", type=Path, help="Path to fixture JSON that mimics 'az vm list-skus' output.")
    check.add_argument("--mock-usage-file", type=Path, help="Path to fixture JSON that mimics 'az vm list-usage' output.")
    check.add_argument(
        "--enable-live-sku-metadata",
        action="store_true",
        help="Opt in to 'az vm list-skus' calls for offered/restricted signals. Disabled by default because the command can hang or time out.",
    )
    return parser


def _build_provider(args: argparse.Namespace) -> AzureCliProvider | FixtureProvider:
    if args.mock_skus_file:
        return FixtureProvider(args.mock_skus_file, args.mock_usage_file)
    if args.mock_usage_file:
        raise ValueError("--mock-usage-file requires --mock-skus-file.")
    return AzureCliProvider(subscription=args.subscription, enable_live_sku_metadata=args.enable_live_sku_metadata)


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


def _render(output: str, rows: list, subscription: str | None) -> str:
    if output == "json":
        return render_json(rows, subscription=subscription)
    if output == "csv":
        return render_csv(rows)
    return render_table(rows)
