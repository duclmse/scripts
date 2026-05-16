"""File-based TTL cache backed by pickle with atomic writes."""
from __future__ import annotations

import hashlib
import os
import pickle
import time
from pathlib import Path
from typing import Any

from .exceptions import CacheError
from .logger import get_logger

log = get_logger("cache")


class Cache:
    """Per-key file cache with TTL.

    Each entry lives in its own ``<sha256-of-key>.pkl`` file under *cache_dir*.
    Writes are atomic (write to ``.tmp`` then ``os.replace``), so concurrent
    readers never see a partial file.
    """

    def __init__(
        self,
        cache_dir: str | None = None,
        default_ttl: int = 300,
    ) -> None:
        if cache_dir is None:
            cache_dir = os.path.join(Path.home(), ".awscli", "cache")
        self.dir = Path(cache_dir)
        self.default_ttl = default_ttl
        self.dir.mkdir(parents=True, exist_ok=True)

    # ── Internals ────────────────────────────────────────────────────────────

    def _path(self, key: str) -> Path:
        digest = hashlib.sha256(key.encode()).hexdigest()
        return self.dir / f"{digest}.pkl"

    # ── Public API ───────────────────────────────────────────────────────────

    def get(self, key: str) -> Any | None:
        """Return the stored value, or *None* if absent or expired."""
        path = self._path(key)
        if not path.exists():
            return None
        try:
            with path.open("rb") as fh:
                entry: dict[str, Any] = pickle.load(fh)
        except Exception as exc:  # noqa: BLE001
            log.warning("cache read error", extra={"key": key, "err": str(exc)})
            return None
        exp = entry.get("exp")
        if exp is not None and time.monotonic() > exp:
            path.unlink(missing_ok=True)
            log.debug("cache miss (expired)", extra={"key": key})
            return None
        log.debug("cache hit", extra={"key": key})
        return entry["val"]

    def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        """Persist *value* under *key* with an optional TTL (seconds).

        ``ttl=0`` means never expire.
        """
        effective = self.default_ttl if ttl is None else ttl
        exp = (time.monotonic() + effective) if effective > 0 else None
        path = self._path(key)
        tmp = path.with_suffix(".tmp")
        try:
            with tmp.open("wb") as fh:
                pickle.dump(
                    {"val": value, "exp": exp, "key": key},
                    fh,
                    protocol=pickle.HIGHEST_PROTOCOL,
                )
            tmp.replace(path)
        except Exception as exc:
            raise CacheError(f"Cache write failed for {key!r}: {exc}") from exc
        log.debug("cache set", extra={"key": key, "ttl": effective})

    def delete(self, key: str) -> bool:
        path = self._path(key)
        if path.exists():
            path.unlink()
            return True
        return False

    def clear(self, prefix: str | None = None) -> int:
        """Delete all entries.  Pass *prefix* to restrict to keys starting with it."""
        deleted = 0
        for path in list(self.dir.glob("*.pkl")):
            if prefix is not None:
                try:
                    with path.open("rb") as fh:
                        entry = pickle.load(fh)
                    if not entry.get("key", "").startswith(prefix):
                        continue
                except Exception:  # noqa: BLE001
                    pass
            path.unlink(missing_ok=True)
            deleted += 1
        log.info("cache cleared", extra={"deleted": deleted, "prefix": prefix})
        return deleted

    def stats(self) -> dict[str, Any]:
        """Return a summary of cache health."""
        total = valid = expired = 0
        now = time.monotonic()
        for path in self.dir.glob("*.pkl"):
            total += 1
            try:
                with path.open("rb") as fh:
                    entry = pickle.load(fh)
                exp = entry.get("exp")
                if exp is None or now <= exp:
                    valid += 1
                else:
                    expired += 1
            except Exception:  # noqa: BLE001
                expired += 1
        return {
            "total": total,
            "valid": valid,
            "expired": expired,
            "dir": str(self.dir),
        }
