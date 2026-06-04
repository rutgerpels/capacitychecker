from __future__ import annotations

import json
import shutil
import subprocess
import threading
from typing import Any, Protocol
from urllib.parse import quote

from .cache import CacheError, CacheStore


RESOURCE_SKUS_API_VERSION = "2021-07-01"
RESOURCE_SKUS_TTL_SECONDS = 3600
USAGE_TTL_SECONDS = 300
SPOT_PLACEMENT_TTL_SECONDS = 120


class CapacityProvider(Protocol):
    def list_skus(self, region: str, sku: str) -> list[dict[str, Any]] | None:
        ...

    def list_usage(self, region: str) -> list[dict[str, Any]]:
        ...

    def list_spot_placement_scores(
        self,
        regions: list[str],
        skus: list[str],
        zones: list[str | None],
        desired_count: int,
    ) -> list[dict[str, Any]] | None:
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
        cache_store: CacheStore | None = None,
        cache_enabled: bool = True,
    ) -> None:
        self.subscription = subscription
        self.enable_live_sku_metadata = enable_live_sku_metadata
        self.az_executable = az_executable
        self.cache_store = cache_store
        self.cache_enabled = cache_enabled
        self._subscription_id: str | None = None
        self._sku_cache: dict[str, list[dict[str, Any]]] = {}
        self._cache_notes = threading.local()
        self._sku_cache_lock = threading.Lock()
        self._subscription_lock = threading.Lock()

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
        with self._sku_cache_lock:
            cached_rows = self._sku_cache.get(cache_key)
        if cached_rows is not None:
            self._add_cache_note(f"ResourceSkus in-memory cache hit for {region}.")
            return cached_rows

        resolved_subscription_id = self._resolve_subscription_id()
        subscription_id = quote(resolved_subscription_id, safe="")
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
        response = self._cached_json(
            "resource-skus",
            {
                "api_version": RESOURCE_SKUS_API_VERSION,
                "subscription": resolved_subscription_id,
                "region": region.casefold(),
            },
            RESOURCE_SKUS_TTL_SECONDS,
            command,
        )
        if not isinstance(response, dict):
            raise ProviderError("Azure Resource SKUs API returned unexpected JSON; expected an object.")

        rows = response.get("value", [])
        if not isinstance(rows, list):
            raise ProviderError("Azure Resource SKUs API returned unexpected JSON; expected a value list.")

        filtered_rows = [row for row in rows if isinstance(row, dict)]
        with self._sku_cache_lock:
            self._sku_cache[cache_key] = filtered_rows
        return filtered_rows

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
        response = self._cached_json(
            "usage",
            {
                "subscription": self._cache_subscription_key(),
                "region": region.casefold(),
            },
            USAGE_TTL_SECONDS,
            command,
        )
        if not isinstance(response, list):
            raise ProviderError("Azure CLI returned unexpected JSON; expected a list.")
        return response

    def list_spot_placement_scores(
        self,
        regions: list[str],
        skus: list[str],
        zones: list[str | None],
        desired_count: int,
    ) -> list[dict[str, Any]] | None:
        availability_zones = any(zone is not None for zone in zones)
        command = [
            self._az_command(),
            "compute-recommender",
            "spot-placement-score",
            "--location",
            regions[0],
            "--availability-zones",
            str(availability_zones).lower(),
            "--desired-locations",
            json.dumps(regions),
            "--desired-count",
            str(desired_count),
            "--desired-sizes",
            json.dumps([{"sku": sku} for sku in skus]),
            "--output",
            "json",
            "--only-show-errors",
        ]
        response = self._cached_json(
            "spot-placement-score",
            {
                "subscription": self._cache_subscription_key(),
                "regions": sorted(region.casefold() for region in regions),
                "skus": sorted(sku.casefold() for sku in skus),
                "availability_zones": availability_zones,
                "desired_count": desired_count,
            },
            SPOT_PLACEMENT_TTL_SECONDS,
            command,
        )
        if not isinstance(response, dict):
            raise ProviderError("Azure Spot Placement Score returned unexpected JSON; expected an object.")

        scores = response.get("placementScores", [])
        if not isinstance(scores, list):
            raise ProviderError("Azure Spot Placement Score returned unexpected JSON; expected a placementScores list.")
        return [score for score in scores if isinstance(score, dict)]

    def _resolve_subscription_id(self) -> str:
        if self._subscription_id:
            return self._subscription_id

        with self._subscription_lock:
            if self._subscription_id:
                return self._subscription_id

            command = [self._az_command(), "account", "show", "--query", "id", "--output", "tsv"]
            self._subscription_id = self._run_text(command).strip()
            if not self._subscription_id:
                raise ProviderError("Azure CLI did not return a subscription id.")
            return self._subscription_id

    def _cache_subscription_key(self) -> str:
        if not self.cache_enabled or self.cache_store is None:
            return self.subscription or "default"
        return self._resolve_subscription_id()

    def cache_notes(self) -> list[str]:
        notes = list(getattr(self._cache_notes, "notes", []))
        self._cache_notes.notes = []
        return notes

    def _add_cache_note(self, note: str) -> None:
        notes = getattr(self._cache_notes, "notes", None)
        if notes is None:
            notes = []
            self._cache_notes.notes = notes
        notes.append(note)

    def _az_command(self) -> str:
        executable = self.az_executable or shutil.which("az")
        if executable:
            return executable
        raise ProviderError("Azure CLI executable 'az' was not found. Install Azure CLI.")

    def _run_text(self, command: list[str]) -> str:
        if self.subscription:
            command.extend(["--subscription", self.subscription])

        try:
            completed = subprocess.run(command, check=False, capture_output=True, text=True, timeout=60)
        except FileNotFoundError as exc:
            raise ProviderError("Azure CLI executable 'az' was not found. Install Azure CLI.") from exc
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

    def _cached_json(
        self,
        namespace: str,
        key_data: dict[str, Any],
        ttl_seconds: int,
        command: list[str],
    ) -> Any:
        if not self.cache_enabled or self.cache_store is None:
            self._add_cache_note(f"{namespace} cache bypassed.")
            return self._run_json(command)

        try:
            cached = self.cache_store.get(namespace, key_data)
        except CacheError as exc:
            raise ProviderError(str(exc)) from exc

        if cached is not None:
            self._add_cache_note(f"{namespace} cache hit; age {cached.age_seconds}s.")
            return cached.value

        self._add_cache_note(f"{namespace} cache miss.")
        response = self._run_json(command)
        try:
            self.cache_store.set(namespace, key_data, response, ttl_seconds)
        except CacheError as exc:
            raise ProviderError(str(exc)) from exc
        return response

def _casefold(value: Any) -> str:
    return str(value or "").casefold()
