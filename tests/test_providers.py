from __future__ import annotations

import subprocess
import unittest
from unittest.mock import patch

from capacitychecker.providers import AzureCliProvider, ProviderError


class AzureCliProviderTests(unittest.TestCase):
    def test_fetches_spot_placement_scores(self) -> None:
        response = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout='{"placementScores":[{"sku":"Standard_D2s_v5","region":"eastus","score":"High","isQuotaAvailable":true}]}',
            stderr="",
        )

        with patch("capacitychecker.providers.subprocess.run", return_value=response) as run:
            scores = AzureCliProvider(az_executable="az").list_spot_placement_scores(
                ["eastus"],
                ["Standard_D2s_v5"],
                [None],
                1,
            )

        self.assertEqual(scores, [{"sku": "Standard_D2s_v5", "region": "eastus", "score": "High", "isQuotaAvailable": True}])
        command = run.call_args.args[0]
        self.assertIn("spot-placement-score", command)
        self.assertIn("--desired-count", command)
        self.assertIn("1", command)
        self.assertIn("--desired-locations", command)
        self.assertIn('["eastus"]', command)
        self.assertIn("--desired-sizes", command)
        self.assertIn('[{"sku": "Standard_D2s_v5"}]', command)
        self.assertIn("--availability-zones", command)
        self.assertIn("false", command)

    def test_fetches_zonal_spot_placement_scores(self) -> None:
        response = subprocess.CompletedProcess(args=[], returncode=0, stdout='{"placementScores":[]}', stderr="")

        with patch("capacitychecker.providers.subprocess.run", return_value=response) as run:
            AzureCliProvider(az_executable="az").list_spot_placement_scores(
                ["eastus"],
                ["Standard_D2s_v5"],
                ["1", "2"],
                3,
            )

        command = run.call_args.args[0]
        self.assertIn("--availability-zones", command)
        self.assertIn("true", command)
        self.assertIn("--desired-count", command)
        self.assertIn("3", command)

    def test_fetches_resource_skus_through_az_rest(self) -> None:
        account = subprocess.CompletedProcess(args=[], returncode=0, stdout="sub-123\n", stderr="")
        skus = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout='{"value":[{"name":"Standard_D2s_v5"},{"name":"Standard_E4s_v5"}]}',
            stderr="",
        )

        with patch("capacitychecker.providers.subprocess.run", side_effect=[account, skus]) as run:
            rows = AzureCliProvider(az_executable="az").list_skus("eastus", "Standard_D2s_v5")

        self.assertEqual(rows, [{"name": "Standard_D2s_v5"}])
        account_command = run.call_args_list[0].args[0]
        rest_command = run.call_args_list[1].args[0]
        self.assertEqual(account_command[:3], ["az", "account", "show"])
        self.assertIn("rest", rest_command)
        self.assertIn("--url", rest_command)
        self.assertIn("Microsoft.Compute/skus", rest_command[rest_command.index("--url") + 1])
        self.assertIn("--url-parameters", rest_command)
        self.assertIn("api-version=2021-07-01", rest_command)
        self.assertIn("$filter=location eq 'eastus'", rest_command)

    def test_caches_resource_skus_by_region(self) -> None:
        account = subprocess.CompletedProcess(args=[], returncode=0, stdout="sub-123\n", stderr="")
        skus = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout='{"value":[{"name":"Standard_D2s_v5"},{"name":"Standard_E4s_v5"}]}',
            stderr="",
        )

        with patch("capacitychecker.providers.subprocess.run", side_effect=[account, skus]) as run:
            provider = AzureCliProvider(az_executable="az")
            self.assertEqual(provider.list_skus("eastus", "Standard_D2s_v5"), [{"name": "Standard_D2s_v5"}])
            self.assertEqual(provider.list_skus("eastus", "Standard_E4s_v5"), [{"name": "Standard_E4s_v5"}])

        self.assertEqual(run.call_count, 2)

    def test_can_skip_live_sku_metadata(self) -> None:
        with patch("capacitychecker.providers.subprocess.run") as run:
            rows = AzureCliProvider(enable_live_sku_metadata=False, az_executable="az").list_skus(
                "eastus",
                "Standard_D2s_v5",
            )

        self.assertIsNone(rows)
        run.assert_not_called()

    def test_resolves_azure_cli_with_windows_command_extension(self) -> None:
        az_cmd = r"C:\Program Files (x86)\Microsoft SDKs\Azure\CLI2\wbin\az.cmd"
        completed = subprocess.CompletedProcess(args=[], returncode=0, stdout="[]", stderr="")

        with (
            patch("capacitychecker.providers.shutil.which", return_value=az_cmd),
            patch("capacitychecker.providers.subprocess.run", return_value=completed) as run,
        ):
            AzureCliProvider(subscription="sub-123").list_usage("eastus")

        command = run.call_args.args[0]
        self.assertEqual(command[0], az_cmd)
        self.assertIn("--subscription", command)
        self.assertIn("sub-123", command)

    def test_missing_azure_cli_reports_provider_error(self) -> None:
        with patch("capacitychecker.providers.shutil.which", return_value=None):
            with self.assertRaisesRegex(ProviderError, "Azure CLI executable 'az' was not found"):
                AzureCliProvider().list_usage("eastus")


if __name__ == "__main__":
    unittest.main()
