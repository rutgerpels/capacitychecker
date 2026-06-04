from __future__ import annotations

import csv
import json
import threading
import tomllib
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from capacitychecker import __version__
from capacitychecker.cache import CacheStore
from capacitychecker.cli import _build_parser, main
from capacitychecker.matrix import build_matrix
from capacitychecker.providers import ProviderError
from capacitychecker.renderers import render_csv, render_json, render_table


class CliTests(unittest.TestCase):
    def run_cli(self, *args: str) -> tuple[int, str, str]:
        stdout = StringIO()
        stderr = StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = main(list(args))
        return code, stdout.getvalue(), stderr.getvalue()

    def test_requires_sku_and_region(self) -> None:
        code, _, stderr = self.run_cli("check", "--sku", "Standard_D2s_v5")

        self.assertEqual(code, 1)
        self.assertIn("region", stderr)

    def test_prints_version(self) -> None:
        code, stdout, stderr = self.run_cli("--version")

        self.assertEqual(code, 0, stderr)
        self.assertEqual(stdout.strip(), __version__)

    def test_no_command_prints_help(self) -> None:
        code, stdout, stderr = self.run_cli()

        self.assertEqual(code, 2)
        self.assertIn("usage: capacitychecker", stdout)
        self.assertEqual(stderr, "")

    def test_live_sku_metadata_is_enabled_by_default_with_opt_out(self) -> None:
        parser = _build_parser()

        default_args = parser.parse_args(["check", "--sku", "Standard_D2s_v5", "--region", "eastus"])
        opt_out_args = parser.parse_args(
            ["check", "--sku", "Standard_D2s_v5", "--region", "eastus", "--skip-live-sku-metadata"]
        )
        spot_args = parser.parse_args(
            [
                "check",
                "--sku",
                "Standard_D2s_v5",
                "--region",
                "eastus",
                "--include-spot-score",
                "--spot-desired-count",
                "2",
            ]
        )

        self.assertTrue(default_args.enable_live_sku_metadata)
        self.assertFalse(opt_out_args.enable_live_sku_metadata)
        self.assertTrue(spot_args.include_spot_score)
        self.assertEqual(spot_args.spot_desired_count, 2)
        self.assertEqual(default_args.max_workers, 4)

    def test_cache_flags_are_available(self) -> None:
        parser = _build_parser()

        args = parser.parse_args(["check", "--sku", "Standard_D2s_v5", "--region", "eastus", "--no-cache"])

        self.assertTrue(args.no_cache)

    def test_max_workers_must_be_positive(self) -> None:
        code, _, stderr = self.run_cli("check", "--sku", "Standard_D2s_v5", "--region", "eastus", "--max-workers", "0")

        self.assertEqual(code, 1)
        self.assertIn("max-workers", stderr)

    def test_cache_info_does_not_require_sku_or_region(self) -> None:
        with TemporaryDirectory() as temp_dir:
            cache = CacheStore(Path(temp_dir), now=lambda: 1000.0)
            with patch("capacitychecker.cli.CacheStore", return_value=cache):
                code, stdout, stderr = self.run_cli("check", "--cache-info")

        self.assertEqual(code, 0, stderr)
        self.assertIn("Cache directory:", stdout)
        self.assertIn("Entries: 0", stdout)

    def test_clear_cache_does_not_require_sku_or_region(self) -> None:
        with TemporaryDirectory() as temp_dir:
            cache = CacheStore(Path(temp_dir), now=lambda: 1000.0)
            cache.set("usage", {"region": "eastus"}, [], ttl_seconds=60)
            with patch("capacitychecker.cli.CacheStore", return_value=cache):
                code, stdout, stderr = self.run_cli("check", "--clear-cache")

        self.assertEqual(code, 0, stderr)
        self.assertIn("Cleared 1 cache entry", stdout)


    def test_provider_errors_are_reported_cleanly(self) -> None:
        class FailingProvider:
            source_name = "failing-test"

            def list_skus(self, region: str, sku: str):
                return []

            def list_usage(self, region: str):
                raise ProviderError("boom")

            def list_spot_placement_scores(self, regions, skus, zones, desired_count):
                return None

        with patch("capacitychecker.cli._build_provider", return_value=FailingProvider()):
            code, stdout, stderr = self.run_cli("check", "--sku", "Standard_D2s_v5", "--region", "eastus")

        self.assertEqual(code, 1)
        self.assertEqual(stdout, "")
        self.assertIn("capacitychecker: error: boom", stderr)

    def test_main_renders_json_output(self) -> None:
        with patch("capacitychecker.cli._build_provider", return_value=StaticCapacityProvider()):
            code, stdout, stderr = self.run_cli(
                "check",
                "--sku",
                "Standard_D2s_v5",
                "--region",
                "eastus",
                "--output",
                "json",
            )

        self.assertEqual(code, 0, stderr)
        payload = json.loads(stdout)
        self.assertEqual(payload["results"][0]["sku"], "Standard_D2s_v5")
        self.assertEqual(payload["results"][0]["allocatable"], "likely_yes")


class PackagingTests(unittest.TestCase):
    def test_pyproject_uses_package_version_attribute(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        pyproject = tomllib.loads((project_root / "pyproject.toml").read_text(encoding="utf-8"))

        self.assertEqual(pyproject["project"]["dynamic"], ["version"])
        self.assertEqual(pyproject["tool"]["setuptools"]["dynamic"]["version"]["attr"], "capacitychecker.__version__")


class QuotaOnlyProvider:
    source_name = "quota-only-test"

    def list_skus(self, region: str, sku: str):
        return None

    def list_usage(self, region: str):
        return [
            {
                "name": {"value": "standardDSv5Family"},
                "currentValue": "4",
                "limit": "20",
            }
        ]

    def list_spot_placement_scores(self, regions, skus, zones, desired_count):
        return None


class StaticCapacityProvider:
    source_name = "static-test"

    def __init__(self) -> None:
        self.skus_data = {
            "eastus": [
                {
                    "name": "Standard_D2s_v5",
                    "locations": ["eastus"],
                    "locationInfo": [{"location": "eastus", "zones": ["1", "2", "3"]}],
                    "restrictions": [],
                },
                {
                    "name": "Standard_E4s_v5",
                    "locations": ["eastus"],
                    "locationInfo": [{"location": "eastus", "zones": ["1", "2", "3"]}],
                    "restrictions": [],
                },
            ],
            "swedencentral": [
                {
                    "name": "Standard_D2s_v5",
                    "locations": ["swedencentral"],
                    "locationInfo": [{"location": "swedencentral", "zones": ["1", "2"]}],
                    "restrictions": [
                        {
                            "type": "Location",
                            "reasonCode": "NotAvailableForSubscription",
                            "restrictionInfo": {"locations": ["swedencentral"]},
                        }
                    ],
                }
            ],
        }
        self.usage_data = {
            "eastus": [
                {
                    "name": {"value": "standardDSv5Family", "localizedValue": "Standard DSv5 Family vCPUs"},
                    "currentValue": "10",
                    "limit": "100",
                    "unit": "Count",
                }
            ],
            "swedencentral": [
                {
                    "name": {"value": "standardDSv5Family", "localizedValue": "Standard DSv5 Family vCPUs"},
                    "currentValue": 10,
                    "limit": 10,
                    "unit": "Count",
                }
            ],
        }

    def list_skus(self, region: str, sku: str):
        return [row for row in self.skus_data.get(region, []) if row["name"].casefold() == sku.casefold()]

    def list_usage(self, region: str):
        return self.usage_data.get(region, [])

    def list_spot_placement_scores(self, regions, skus, zones, desired_count):
        return None


class SpotScoreProvider:
    source_name = "spot-score-test"

    def list_skus(self, region: str, sku: str):
        return [
            {
                "name": sku,
                "locations": [region],
                "locationInfo": [{"location": region, "zones": ["1"]}],
                "restrictions": [],
            }
        ]

    def list_usage(self, region: str):
        return [
            {
                "name": {"value": "standardDSv5Family"},
                "currentValue": "4",
                "limit": "20",
            }
        ]

    def list_spot_placement_scores(self, regions, skus, zones, desired_count):
        return [
            {
                "sku": "Standard_D2s_v5",
                "region": "eastus",
                "availabilityZone": "1",
                "score": "High",
                "isQuotaAvailable": True,
            }
        ]


class TrackingProvider:
    source_name = "tracking-test"

    def __init__(self) -> None:
        self.active_usage_calls = 0
        self.max_active_usage_calls = 0
        self.lock = threading.Lock()
        self.two_active_calls = threading.Event()

    def list_skus(self, region: str, sku: str):
        return [{"name": sku, "locations": [region], "locationInfo": [{"location": region, "zones": []}], "restrictions": []}]

    def list_usage(self, region: str):
        with self.lock:
            self.active_usage_calls += 1
            self.max_active_usage_calls = max(self.max_active_usage_calls, self.active_usage_calls)
            if self.active_usage_calls >= 2:
                self.two_active_calls.set()
        try:
            self.two_active_calls.wait(timeout=1)
            return [{"name": {"value": "standardDSv5Family"}, "currentValue": "1", "limit": "10"}]
        finally:
            with self.lock:
                self.active_usage_calls -= 1

    def list_spot_placement_scores(self, regions, skus, zones, desired_count):
        return None


class MatrixTests(unittest.TestCase):
    def test_table_output_uses_static_provider_data(self) -> None:
        rows = build_matrix(StaticCapacityProvider(), ["Standard_D2s_v5"], ["eastus"], [None])
        stdout = render_table(rows)

        self.assertIn("Standard_D2s_v5", stdout)
        self.assertIn("eastus", stdout)
        self.assertIn("likely_yes", stdout)
        self.assertIn("90 vCPU", stdout)

    def test_json_output_marks_restricted_region_likely_no(self) -> None:
        rows = build_matrix(StaticCapacityProvider(), ["Standard_D2s_v5"], ["swedencentral"], [None])
        payload = json.loads(render_json(rows))
        row = payload["results"][0]

        self.assertIn("allocatable_confidence", row)
        self.assertIn("data_source", row)
        self.assertTrue(row["offered"])
        self.assertTrue(row["capacity_restricted"])
        self.assertEqual(row["allocatable"], "likely_no")
        self.assertEqual(row["quota_headroom"]["value"], 0)

    def test_csv_output_is_parseable(self) -> None:
        rows = build_matrix(StaticCapacityProvider(), ["Standard_D2s_v5"], ["eastus"], [None])
        csv_rows = list(csv.DictReader(StringIO(render_csv(rows))))

        self.assertEqual(len(csv_rows), 1)
        self.assertEqual(csv_rows[0]["SKU"], "Standard_D2s_v5")
        self.assertEqual(csv_rows[0]["Allocatable"], "likely_yes")

    def test_zone_not_offered_returns_no(self) -> None:
        rows = build_matrix(StaticCapacityProvider(), ["Standard_D2s_v5"], ["swedencentral"], ["3"])

        self.assertFalse(rows[0].offered)
        self.assertEqual(rows[0].allocatable, "no")

    def test_live_quota_only_mode_marks_sku_metadata_unknown(self) -> None:
        rows = build_matrix(QuotaOnlyProvider(), ["Standard_D2s_v5"], ["eastus"], [None])

        self.assertEqual(len(rows), 1)
        self.assertIsNone(rows[0].offered)
        self.assertIsNone(rows[0].capacity_restricted)
        self.assertEqual(rows[0].quota_headroom.value, 16)
        self.assertEqual(rows[0].allocatable, "unknown")
        self.assertEqual(rows[0].confidence, "low")

    def test_spot_score_adds_guidance_without_overriding_regular_allocatable(self) -> None:
        rows = build_matrix(
            SpotScoreProvider(),
            ["Standard_D2s_v5"],
            ["eastus"],
            ["1"],
            include_spot_score=True,
            spot_desired_count=1,
        )

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].spot_placement_score, "High")
        self.assertEqual(rows[0].spot_placement_guidance, "high")
        self.assertTrue(rows[0].spot_quota_available)
        self.assertEqual(rows[0].allocatable, "likely_yes")
        self.assertIn("not a guarantee", " ".join(rows[0].notes))

    def test_build_matrix_parallelizes_regions_with_worker_limit(self) -> None:
        provider = TrackingProvider()

        rows = build_matrix(
            provider,
            ["Standard_D2s_v5"],
            ["eastus", "westus2", "centralus", "swedencentral"],
            [None],
            max_workers=2,
        )

        self.assertEqual(len(rows), 4)
        self.assertEqual([row.region for row in rows], ["eastus", "westus2", "centralus", "swedencentral"])
        self.assertGreaterEqual(provider.max_active_usage_calls, 2)
        self.assertLessEqual(provider.max_active_usage_calls, 2)


if __name__ == "__main__":
    unittest.main()
