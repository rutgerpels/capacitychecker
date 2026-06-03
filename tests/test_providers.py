from __future__ import annotations

import subprocess
import unittest
from unittest.mock import patch

from capacitychecker.providers import AzureCliProvider, ProviderError


class AzureCliProviderTests(unittest.TestCase):
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
