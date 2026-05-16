"""AppContext — the shared object stored in Click's ``ctx.obj``."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from core.logger import Logger

from .auth import Auth
from .cache import Cache
from .config import Config
import sys

from .exceptions import DryRunAbort
from .output import print_output


@dataclass
class AppContext:
    """Central context object injected into every Click command via ``pass_obj``."""

    config: Config
    auth: Auth
    cache: Cache

    # Global CLI flags — may differ from config defaults when overridden on CLI.
    profile: str | None = None
    region: str | None = None
    role: str | None = None
    output: str = "table"
    dry_run: bool = False
    no_cache: bool = False
    yes: bool = False       # skip interactive confirmations
    verbose: bool = False

    # ── Client factory ────────────────────────────────────────────────────────

    def client(self, service: str, region: str | None = None) -> Any:
        """Return a boto3 service client using the current auth context."""
        return self.auth.client(
            service,
            profile=self.profile,
            region=region or self.region,
            role=self.role,
        )

    # ── Cache helpers ─────────────────────────────────────────────────────────

    def cached(
        self,
        key: str,
        fn: Callable[..., Any],
        *args: Any,
        ttl: int | None = None,
        **kwargs: Any,
    ) -> Any:
        """Call *fn* and cache its return value under *key*.

        Bypassed entirely when ``--no-cache`` is active.
        """
        if self.no_cache:
            return fn(*args, **kwargs)
        hit = self.cache.get(key)
        if hit is not None:
            return hit
        result = fn(*args, **kwargs)
        self.cache.set(key, result, ttl=ttl)
        return result

    # ── Dry-run / confirmation gate ───────────────────────────────────────────

    def guard(self, operation: str, details: str = "", destructive: bool = False) -> None:
        """Gate a mutating operation.

        In dry-run mode: print a notice and raise :class:`DryRunAbort`.
        When ``destructive=True`` and not in dry-run: prompt for confirmation
        unless ``--yes`` was passed.
        """

        if self.dry_run:
            msg = f"[DRY RUN] Would execute: {operation}"
            if details:
                msg += f"  ({details})"
            Logger.warn(msg)
            sys.exit(0)  # exit code 0 — no error, just a preview

        if destructive and not self.yes:
            Logger.error(f"'{operation}' is destructive and cannot be undone. Continue?")

    # ── Output helper ─────────────────────────────────────────────────────────

    def out(self, data: Any) -> None:
        """Print *data* using the currently selected output format."""
        print_output(data, self.output)
