from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Callable


DEFAULT_CACHE_DIR = Path.home() / ".capacitychecker" / "cache"


class CacheError(RuntimeError):
    pass


@dataclass(frozen=True)
class CacheEntryInfo:
    namespace: str
    cache_key: str
    path: Path
    created_at: float
    expires_at: float
    expired: bool


@dataclass(frozen=True)
class CacheRead:
    value: Any
    age_seconds: int


class CacheStore:
    def __init__(self, cache_dir: Path | None = None, now: Callable[[], float] | None = None) -> None:
        self.cache_dir = cache_dir or DEFAULT_CACHE_DIR
        self._now = now or time.time

    def get(self, namespace: str, key_data: dict[str, Any]) -> CacheRead | None:
        path = self._path(namespace, key_data)
        if not path.exists():
            return None

        entry = self._read_entry(path)
        now = self._now()
        if _float(entry.get("expires_at")) <= now:
            return None

        created_at = _float(entry.get("created_at"))
        return CacheRead(value=entry.get("value"), age_seconds=max(int(now - created_at), 0))

    def set(self, namespace: str, key_data: dict[str, Any], value: Any, ttl_seconds: int) -> None:
        path = self._path(namespace, key_data)
        path.parent.mkdir(parents=True, exist_ok=True)
        now = self._now()
        entry = {
            "namespace": namespace,
            "cache_key": _cache_key(key_data),
            "key": _normalize_json(key_data),
            "created_at": now,
            "expires_at": now + ttl_seconds,
            "value": value,
        }

        with NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=path.parent, suffix=".tmp") as temp_file:
            temp_path = Path(temp_file.name)
            json.dump(entry, temp_file, indent=2, sort_keys=True)
        temp_path.replace(path)

    def clear(self) -> int:
        if not self.cache_dir.exists():
            return 0

        count = 0
        for path in self.cache_dir.rglob("*.json"):
            path.unlink()
            count += 1
        return count

    def describe(self) -> list[CacheEntryInfo]:
        if not self.cache_dir.exists():
            return []

        now = self._now()
        entries: list[CacheEntryInfo] = []
        for path in sorted(self.cache_dir.rglob("*.json")):
            entry = self._read_entry(path)
            expires_at = _float(entry.get("expires_at"))
            entries.append(
                CacheEntryInfo(
                    namespace=str(entry.get("namespace") or path.parent.name),
                    cache_key=str(entry.get("cache_key") or path.stem),
                    path=path,
                    created_at=_float(entry.get("created_at")),
                    expires_at=expires_at,
                    expired=expires_at <= now,
                )
            )
        return entries

    def path(self) -> Path:
        return self.cache_dir

    def _path(self, namespace: str, key_data: dict[str, Any]) -> Path:
        return self.cache_dir / namespace / f"{_cache_key(key_data)}.json"

    def _read_entry(self, path: Path) -> dict[str, Any]:
        try:
            entry = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise CacheError(f"Cache entry contains invalid JSON: {path}") from exc
        except OSError as exc:
            raise CacheError(f"Cache entry could not be read: {path}") from exc

        if not isinstance(entry, dict) or "value" not in entry:
            raise CacheError(f"Cache entry has an unexpected shape: {path}")
        return entry


def _cache_key(key_data: dict[str, Any]) -> str:
    payload = json.dumps(_normalize_json(key_data), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _normalize_json(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _normalize_json(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        return [_normalize_json(item) for item in value]
    return value


def _float(value: Any) -> float:
    if isinstance(value, int | float):
        return float(value)
    raise CacheError("Cache entry is missing numeric timestamp metadata.")
