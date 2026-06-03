from __future__ import annotations

import csv
import json
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

from capacitychecker.cli import main
from capacitychecker.matrix import build_matrix


ROOT = Path(__file__).resolve().parent
SKUS_FIXTURE = ROOT / "fixtures" / "skus.json"
USAGE_FIXTURE = ROOT / "fixtures" / "usage.json"


class CliTests(unittest.TestCase):
    def run_cli(self, *args: str) -> tuple[int, str, str]:
        stdout = StringIO()
        stderr = StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = main(list(args))
        return code, stdout.getvalue(), stderr.getvalue()

    def test_table_output_uses_fixture_data(self) -> None:
        code, stdout, stderr = self.run_cli(
            "check",
            "--sku",
            "Standard_D2s_v5",
            "--region",
            "eastus",
            "--mock-skus-file",
            str(SKUS_FIXTURE),
            "--mock-usage-file",
            str(USAGE_FIXTURE),
        )

        self.assertEqual(code, 0, stderr)
        self.assertIn("Standard_D2s_v5", stdout)
        self.assertIn("eastus", stdout)
        self.assertIn("likely_yes", stdout)
        self.assertIn("90 vCPU", stdout)

    def test_json_output_marks_restricted_region_likely_no(self) -> None:
        code, stdout, stderr = self.run_cli(
            "check",
            "--skus",
            "Standard_D2s_v5",
            "--regions",
            "swedencentral",
            "--output",
            "json",
            "--mock-skus-file",
            str(SKUS_FIXTURE),
            "--mock-usage-file",
            str(USAGE_FIXTURE),
        )

        self.assertEqual(code, 0, stderr)
        payload = json.loads(stdout)
        row = payload["results"][0]
        self.assertIn("allocatable_confidence", row)
        self.assertIn("data_source", row)
        self.assertTrue(row["offered"])
        self.assertTrue(row["capacity_restricted"])
        self.assertEqual(row["allocatable"], "likely_no")
        self.assertEqual(row["quota_headroom"]["value"], 0)

    def test_csv_output_is_parseable(self) -> None:
        code, stdout, stderr = self.run_cli(
            "check",
            "--sku",
            "Standard_D2s_v5",
            "--region",
            "eastus",
            "--output",
            "csv",
            "--mock-skus-file",
            str(SKUS_FIXTURE),
            "--mock-usage-file",
            str(USAGE_FIXTURE),
        )

        self.assertEqual(code, 0, stderr)
        rows = list(csv.DictReader(StringIO(stdout)))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["SKU"], "Standard_D2s_v5")
        self.assertEqual(rows[0]["Allocatable"], "likely_yes")

    def test_zone_not_offered_returns_no(self) -> None:
        code, stdout, stderr = self.run_cli(
            "check",
            "--sku",
            "Standard_D2s_v5",
            "--region",
            "swedencentral",
            "--zones",
            "3",
            "--output",
            "json",
            "--mock-skus-file",
            str(SKUS_FIXTURE),
            "--mock-usage-file",
            str(USAGE_FIXTURE),
        )

        self.assertEqual(code, 0, stderr)
        row = json.loads(stdout)["results"][0]
        self.assertFalse(row["offered"])
        self.assertEqual(row["allocatable"], "no")

    def test_requires_sku_and_region(self) -> None:
        code, _, stderr = self.run_cli("check", "--sku", "Standard_D2s_v5")

        self.assertEqual(code, 1)
        self.assertIn("region", stderr)


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


class MatrixTests(unittest.TestCase):
    def test_live_quota_only_mode_marks_sku_metadata_unknown(self) -> None:
        rows = build_matrix(QuotaOnlyProvider(), ["Standard_D2s_v5"], ["eastus"], [None])

        self.assertEqual(len(rows), 1)
        self.assertIsNone(rows[0].offered)
        self.assertIsNone(rows[0].capacity_restricted)
        self.assertEqual(rows[0].quota_headroom.value, 16)
        self.assertEqual(rows[0].allocatable, "unknown")
        self.assertEqual(rows[0].confidence, "low")


if __name__ == "__main__":
    unittest.main()
