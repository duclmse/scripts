"""YAML configuration with environment-variable overrides.

Layer precedence (highest wins):
  1. Environment variables (``AWSCLI_*``)
  2. YAML config file
  3. Built-in defaults
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

from .exceptions import ConfigError
from .logger import get_logger

log = get_logger("config")

_DEFAULTS: dict[str, Any] = {
    "region": "us-east-1",
    "profile": None,
    "role": None,
    "output": "table",
    "log_level": "INFO",
    "cache_ttl": 300,
    "cache_enabled": True,
    "dry_run": False,
    "confirm_destructive": True,
    "max_results": 100,
}

# Maps env-var name → config key
_ENV_MAP: dict[str, str] = {
    "AWSCLI_REGION": "region",
    "AWSCLI_PROFILE": "profile",
    "AWSCLI_ROLE": "role",
    "AWSCLI_OUTPUT": "output",
    "AWSCLI_LOG_LEVEL": "log_level",
    "AWSCLI_DRY_RUN": "dry_run",
    "AWSCLI_CACHE_TTL": "cache_ttl",
}

_BOOL_MAP = {
    "true": True, "1": True, "yes": True,
    "false": False, "0": False, "no": False,
}


class Config:
    """Layered configuration: defaults → YAML file → environment variables."""

    def __init__(self, path: str | None = None) -> None:
        self._data: dict[str, Any] = dict(_DEFAULTS)
        self._roles: dict[str, str] = {}

        resolved = path or self._discover()
        if resolved and Path(resolved).exists():
            self._load(resolved)

        self._apply_env()

    # ── Discovery ─────────────────────────────────────────────────────────────

    @staticmethod
    def _discover() -> str | None:
        candidates = [
            Path.cwd() / ".awscli.yaml",
            Path.cwd() / "awscli.yaml",
            Path.home() / ".awscli" / "config.yaml",
            Path.home() / ".config" / "awscli" / "config.yaml",
        ]
        for p in candidates:
            if p.exists():
                return str(p)
        return None

    def _load(self, path: str) -> None:
        try:
            with open(path) as fh:
                raw: dict[str, Any] = yaml.safe_load(fh) or {}
        except yaml.YAMLError as exc:
            raise ConfigError(f"Invalid YAML in {path}: {exc}") from exc
        except OSError as exc:
            raise ConfigError(f"Cannot read config {path}: {exc}") from exc

        self._roles = raw.pop("roles", {})
        self._data.update(raw)
        log.info("config loaded", extra={"path": path})

    def _apply_env(self) -> None:
        for env_key, cfg_key in _ENV_MAP.items():
            raw = os.environ.get(env_key)
            if raw is not None:
                self._data[cfg_key] = _BOOL_MAP.get(raw.lower(), raw)

    # ── Access ────────────────────────────────────────────────────────────────

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value

    def role_arn(self, alias_or_arn: str | None) -> str | None:
        """Resolve a role alias to its ARN; pass-through if it already looks like an ARN."""
        if not alias_or_arn:
            return None
        if alias_or_arn.startswith("arn:"):
            return alias_or_arn
        return self._roles.get(alias_or_arn)

    def as_dict(self) -> dict[str, Any]:
        return {**self._data, "roles": dict(self._roles)}
