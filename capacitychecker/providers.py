from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, Protocol


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
    def __init__(self, subscription: str | None = None, enable_live_sku_metadata: bool = False) -> None:
        self.subscription = subscription
        self.enable_live_sku_metadata = enable_live_sku_metadata

    @property
    def source_name(self) -> str:
        return "azure-cli"

    def list_skus(self, region: str, sku: str) -> list[dict[str, Any]] | None:
        if not self.enable_live_sku_metadata:
            return None
        command = ["az", "vm", "list-skus", "--location", region, "--size", sku, "--all", "--output", "json"]
        return self._run_json(command)

    def list_usage(self, region: str) -> list[dict[str, Any]]:
        command = ["az", "vm", "list-usage", "--location", region, "--output", "json"]
        return self._run_json(command)

    def _run_json(self, command: list[str]) -> list[dict[str, Any]]:
        if self.subscription:
            command.extend(["--subscription", self.subscription])

        try:
            completed = subprocess.run(command, check=False, capture_output=True, text=True, timeout=60)
        except FileNotFoundError as exc:
            raise ProviderError("Azure CLI executable 'az' was not found. Install Azure CLI or use mock fixture files.") from exc
        except subprocess.TimeoutExpired as exc:
            raise ProviderError(f"Azure CLI command timed out: {' '.join(command)}") from exc

        if completed.returncode != 0:
            message = completed.stderr.strip() or completed.stdout.strip() or "unknown Azure CLI error"
            raise ProviderError(f"Azure CLI command failed: {message}")

        try:
            data = json.loads(completed.stdout or "[]")
        except json.JSONDecodeError as exc:
            raise ProviderError("Azure CLI returned invalid JSON.") from exc

        if not isinstance(data, list):
            raise ProviderError("Azure CLI returned unexpected JSON; expected a list.")
        return data


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
