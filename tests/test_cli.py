from __future__ import annotations

import csv
import json
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO

from capacitychecker.cli import _build_parser, main
from capacitychecker.matrix import build_matrix
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


if __name__ == "__main__":
    unittest.main()
