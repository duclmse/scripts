"""Output formatters: table (tabulate), JSON, YAML, CSV."""
from __future__ import annotations

import json
import sys
from typing import Any

import yaml

try:
    from tabulate import tabulate as _tabulate

    _HAS_TABULATE = True
except ImportError:
    _HAS_TABULATE = False


# ── Helpers ──────────────────────────────────────────────────────────────────


def _normalise(data: Any) -> tuple[list[str], list[list[Any]]]:
    """Return *(headers, rows)* suitable for tabulate / CSV."""
    if isinstance(data, dict):
        return list(data.keys()), [list(data.values())]
    if isinstance(data, list) and data:
        if isinstance(data[0], dict):
            # Collect all keys from all rows so we handle sparse dicts.
            headers: list[str] = list(dict.fromkeys(k for row in data for k in row))
            rows = [[row.get(h, "") for h in headers] for row in data]
            return headers, rows
        # Flat list of scalars.
        return ["value"], [[v] for v in data]
    if isinstance(data, list):
        return [], []
    return ["value"], [[data]]


# ── Public API ────────────────────────────────────────────────────────────────


def render(data: Any, fmt: str = "table") -> str:
    """Serialise *data* to a string in the requested *fmt*."""
    fmt = (fmt or "table").lower()

    if fmt == "json":
        return json.dumps(data, indent=2, default=str)

    if fmt in ("yaml", "yml"):
        return yaml.dump(data, default_flow_style=False, allow_unicode=True).rstrip()

    if fmt == "csv":
        headers, rows = _normalise(data)
        if not headers:
            return ""

        def _cell(v: Any) -> str:
            s = str(v)
            return f'"{s}"' if ("," in s or '"' in s or "\n" in s) else s

        lines = [",".join(headers)]
        lines += [",".join(_cell(v) for v in row) for row in rows]
        return "\n".join(lines)

    # Default: table
    if _HAS_TABULATE:
        headers, rows = _normalise(data)
        if not headers:
            return "(empty)"
        return _tabulate(rows, headers=headers, tablefmt="rounded_outline")

    # Fallback when tabulate is not installed.
    return json.dumps(data, indent=2, default=str)


def print_output(data: Any, fmt: str = "table", file: Any = None) -> None:
    """Render *data* and print it to *file* (default: stdout)."""
    file = file or sys.stdout
    print(render(data, fmt), file=file)
