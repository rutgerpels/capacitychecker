from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import quote


RESOURCE_SKUS_API_VERSION = "2021-07-01"


class CapacityProvider(Protocol):
    def list_skus(self, region: str, sku: str) -> list[dict[str, Any]] | None:
        ...

    def list_usage(self, region: str) -> list[dict[str, Any]]:
        ...

    @property
    def source_name(self) -> str:
        ...


class ProviderError(RuntimeError):
    pass


class AzureCliProvider:
    def __init__(
        self,
        subscription: str | None = None,
        enable_live_sku_metadata: bool = True,
        az_executable: str | None = None,
    ) -> None:
        self.subscription = subscription
        self.enable_live_sku_metadata = enable_live_sku_metadata
        self.az_executable = az_executable
        self._subscription_id: str | None = None
        self._sku_cache: dict[str, list[dict[str, Any]]] = {}

    @property
    def source_name(self) -> str:
        return "azure-cli"

    def list_skus(self, region: str, sku: str) -> list[dict[str, Any]] | None:
        if not self.enable_live_sku_metadata:
            return None
        rows = self._resource_skus(region)
        return [row for row in rows if _casefold(row.get("name")) == _casefold(sku)]

    def _resource_skus(self, region: str) -> list[dict[str, Any]]:
        cache_key = region.casefold()
        cached_rows = self._sku_cache.get(cache_key)
        if cached_rows is not None:
             return cached_rows

        subscription_id = quote(self._resolve_subscription_id(), safe="")
        url = (
            f"https://management.azure.com/subscriptions/{subscription_id}"
            "/providers/Microsoft.Compute/skus"
        )
        command = [
            self._az_command(),
            "rest",
            "--method",
            "get",
            "--url",
            url,
            "--url-parameters",
            f"api-version={RESOURCE_SKUS_API_VERSION}",
            f"$filter=location eq '{region}'",
            "--output",
            "json",
        ]
        response = self._run_json(command)
        if not isinstance(response, dict):
            raise ProviderError("Azure Resource SKUs API returned unexpected JSON; expected an object.")

        rows = response.get("value", [])
        if not isinstance(rows, list):
            raise ProviderError("Azure Resource SKUs API returned unexpected JSON; expected a value list.")

        self._sku_cache[cache_key] = [row for row in rows if isinstance(row, dict)]
        return self._sku_cache[cache_key]

    def list_usage(self, region: str) -> list[dict[str, Any]]:
        command = [
            self._az_command(),
            "vm",
            "list-usage",
            "--location",
            region,
            "--output",
            "json",
        ]
        response = self._run_json(command)
        if not isinstance(response, list):
            raise ProviderError("Azure CLI returned unexpected JSON; expected a list.")
        return response

    def _resolve_subscription_id(self) -> str:
        if self._subscription_id:
            return self._subscription_id

        command = [self._az_command(), "account", "show", "--query", "id", "--output", "tsv"]
        self._subscription_id = self._run_text(command).strip()
        if not self._subscription_id:
            raise ProviderError("Azure CLI did not return a subscription id.")
        return self._subscription_id

    def _az_command(self) -> str:
        executable = self.az_executable or shutil.which("az")
        if executable:
            return executable
        raise ProviderError(
            "Azure CLI executable 'az' was not found. Install Azure CLI or use mock fixture files."
        )

    def _run_text(self, command: list[str]) -> str:
        if self.subscription:
            command.extend(["--subscription", self.subscription])

        try:
            completed = subprocess.run(command, check=False, capture_output=True, text=True, timeout=60)
        except FileNotFoundError as exc:
            raise ProviderError(
                "Azure CLI executable 'az' was not found. Install Azure CLI or use mock fixture files."
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise ProviderError(f"Azure CLI command timed out: {' '.join(command)}") from exc

        if completed.returncode != 0:
            message = completed.stderr.strip() or completed.stdout.strip() or "unknown Azure CLI error"
            raise ProviderError(f"Azure CLI command failed: {message}")

        return completed.stdout

    def _run_json(self, command: list[str]) -> Any:
        stdout = self._run_text(command)
        try:
            return json.loads(stdout or "[]")
        except json.JSONDecodeError as exc:
            raise ProviderError("Azure CLI returned invalid JSON.") from exc


class FixtureProvider:
    def __init__(self, skus_file: Path, usage_file: Path | None = None) -> None:
        self.skus_data = _read_json(skus_file)
        self.usage_data = _read_json(usage_file) if usage_file else {}

    @property
    def source_name(self) -> str:
        return "fixture"

    def list_skus(self, region: str, sku: str) -> list[dict[str, Any]]:
        rows = _select_region_rows(self.skus_data, region)
        return [row for row in rows if _casefold(row.get("name")) == _casefold(sku)]

    def list_usage(self, region: str) -> list[dict[str, Any]]:
        return _select_region_rows(self.usage_data, region)


def _read_json(path: Path | None) -> Any:
    if path is None:
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ProviderError(f"Fixture file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ProviderError(f"Fixture file contains invalid JSON: {path}") from exc


def _select_region_rows(data: Any, region: str) -> list[dict[str, Any]]:
    if isinstance(data, dict):
        rows = data.get(region, [])
    else:
        rows = data

    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, dict)]


def _casefold(value: Any) -> str:
    return str(value or "").casefold()
