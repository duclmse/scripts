"""LazyGroup — a Click Group subclass that discovers and loads plugins on demand.

Each plugin module lives under ``aws/plugins/`` and **must** expose a
module-level ``group`` attribute (a :class:`click.Group` instance).  The
group's ``name`` attribute defines the CLI sub-command name.

Lazy loading means:
* Startup time is proportional only to the invoked sub-command, not all plugins.
* Adding a new plugin requires nothing more than dropping a new file into
  ``aws/plugins/`` — no registration step needed.
"""
from __future__ import annotations

import importlib
import pkgutil
from pathlib import Path

from core.logger import Logger

from ..exceptions import AWSCLIError, DryRunAbort

_PLUGIN_PKG = "aws.plugins"
_PLUGIN_DIR = Path(__file__).parent.parent / "plugins"


def _iter_plugin_names() -> list[str]:
    names = []
    for info in pkgutil.iter_modules([str(_PLUGIN_DIR)]):
        if not info.name.startswith("_"):
            # Normalise: "lambda_" → "lambda" for the CLI name
            names.append(info.name.rstrip("_"))
    return names


def _load(name: str):
    """Import the plugin module and return its ``group`` attribute."""
    # Try exact name first, then with trailing underscore (e.g. lambda_).
    for candidate in (name, f"{name}_"):
        try:
            mod = importlib.import_module(f"{_PLUGIN_PKG}.{candidate}")
            grp = getattr(mod, "group", None)
            if grp is not None:
                return grp
        except ImportError:
            continue
    return None


class LazyGroup():
    """Click Group that lazily imports plugin sub-commands."""

    def invoke(self, ctx):
        try:
            return super().invoke(ctx)
        except DryRunAbort as exc:
            Logger.warn(f"[DRY RUN] {exc}")
            ctx.exit(0)
        except AWSCLIError as exc:
            Logger.error(f"Error: {exc}")
            if exc.details:
                Logger.error(f"  {exc.details}")
            ctx.exit(exc.exit_code)

    def list_commands(self, ctx) -> list[str]:
        # Statically registered commands (whoami, cache-cmd, etc.) come first.
        builtins = list(super().list_commands(ctx))
        plugins = [n for n in _iter_plugin_names() if n not in builtins]
        return builtins + plugins

    def get_command(self, ctx, name):
        cmd = super().get_command(ctx, name)
        if cmd is not None:
            return cmd
        return _load(name)
