"""Recursive JSON & YAML → SQLite importer.

Usage:
    python data_to_sqlite.py <folder_path> <db_path>
"""

import argparse
import json
import logging
import re
import sqlite3
import sys
from pathlib import Path
from typing import Any

import yaml

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Type helpers
# ---------------------------------------------------------------------------

Record = dict[str, Any]

_PY_TO_SQL: dict[type, str] = {
    bool: "INTEGER",
    int: "INTEGER",
    float: "REAL",
}


def _sql_type(value: Any) -> str:
    """Map a Python value to a SQLite column type."""
    for py_type, sql in _PY_TO_SQL.items():
        if isinstance(value, py_type):  # bool checked before int via dict order
            return sql
    return "TEXT"


def _flatten(record: Record) -> Record:
    """Serialise nested dicts/lists to JSON strings; leave scalars as-is."""
    return {
        k: json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v
        for k, v in record.items()
    }


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def _parse_json(path: Path) -> list[Record]:
    text = path.read_text(encoding="utf-8")
    if not text.strip():
        return []
    data = json.loads(text)
    if isinstance(data, dict):
        return [data]
    if isinstance(data, list):
        if not data:
            return []
        if not all(isinstance(r, dict) for r in data):
            raise ValueError("JSON array must contain only objects")
        return data
    raise ValueError(f"Unsupported JSON shape: {type(data).__name__}")


def _parse_yaml(path: Path) -> list[Record]:
    text = path.read_text(encoding="utf-8")
    if not text.strip():
        return []
    records: list[Record] = []
    for doc in yaml.safe_load_all(text):
        if doc is None:
            continue
        if isinstance(doc, dict):
            records.append(doc)
        elif isinstance(doc, list):
            if not all(isinstance(r, dict) for r in doc):
                raise ValueError("YAML list must contain only mappings")
            records.extend(doc)
        else:
            raise ValueError(f"Unsupported YAML document shape: {type(doc).__name__}")
    return records


# ---------------------------------------------------------------------------
# Schema / table-name helpers
# ---------------------------------------------------------------------------

def _schema_fingerprint(records: list[Record]) -> str:
    keys: set[str] = set()
    for r in records:
        keys.update(r.keys())
    return ",".join(sorted(keys))


def _sanitise_stem(stem: str) -> str:
    name = stem.lower()
    name = re.sub(r"[^a-z0-9 _-]", "_", name)
    name = re.sub(r"[^a-z0-9]+", "_", name)
    name = name.strip("_")
    return name or "data"


def _unique_name(base: str, taken: set[str]) -> str:
    if base not in taken:
        return base
    i = 1
    while f"{base}_{i}" in taken:
        i += 1
    return f"{base}_{i}"


# ---------------------------------------------------------------------------
# Database operations
# ---------------------------------------------------------------------------

def _setup_db(conn: sqlite3.Connection) -> None:
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS _imported_files (
            file_path   TEXT PRIMARY KEY,
            imported_at TEXT DEFAULT (datetime('now')),
            table_name  TEXT
        )
        """
    )
    conn.commit()


def _load_registry(conn: sqlite3.Connection) -> tuple[dict[str, str], dict[str, str]]:
    """Return (fingerprint→table_name, table_name→fingerprint) from _imported_files."""
    fp_to_tbl: dict[str, str] = {}
    tbl_to_fp: dict[str, str] = {}
    rows = conn.execute(
        "SELECT DISTINCT table_name FROM _imported_files WHERE table_name IS NOT NULL"
    ).fetchall()
    # We need the fingerprint per table; store it in a side-channel using
    # table_info to reconstruct column sets (good enough for name dedup).
    # We keep fp_to_tbl empty here — it'll be filled on first encounter per run.
    for (tbl,) in rows:
        try:
            cols = [r[1] for r in conn.execute(f'PRAGMA table_info("{tbl}")').fetchall()]
            fp = ",".join(sorted(cols))
            fp_to_tbl[fp] = tbl
            tbl_to_fp[tbl] = fp
        except Exception:
            pass
    return fp_to_tbl, tbl_to_fp


def _already_imported(conn: sqlite3.Connection, file_path: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM _imported_files WHERE file_path = ?", (file_path,)
    ).fetchone()
    return row is not None


def _mark_imported(conn: sqlite3.Connection, file_path: str, table_name: str) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO _imported_files (file_path, table_name) VALUES (?, ?)",
        (file_path, table_name),
    )


def _ensure_table(conn: sqlite3.Connection, table: str, records: list[Record]) -> None:
    """Create table or add missing columns as needed."""
    existing: set[str] = {
        r[1] for r in conn.execute(f'PRAGMA table_info("{table}")').fetchall()
    }

    if not existing:
        # Derive column types from first non-null occurrence of each key
        col_types: dict[str, str] = {}
        for rec in records:
            for k, v in rec.items():
                if k not in col_types:
                    col_types[k] = _sql_type(v)

        cols_ddl = ", ".join(f'"{c}" {t}' for c, t in col_types.items())
        conn.execute(f'CREATE TABLE IF NOT EXISTS "{table}" ({cols_ddl})')
        log.info("Created table '%s' with columns: %s", table, list(col_types))
        conn.commit()
        return

    # Add missing columns
    for rec in records:
        for k, v in rec.items():
            if k not in existing:
                sql_t = _sql_type(v)
                conn.execute(f'ALTER TABLE "{table}" ADD COLUMN "{k}" {sql_t}')
                log.info("Added column '%s' (%s) to table '%s'", k, sql_t, table)
                existing.add(k)
    conn.commit()


def _insert_records(
    conn: sqlite3.Connection, table: str, records: list[Record]
) -> int:
    inserted = 0
    for rec in records:
        flat = _flatten(rec)
        cols = list(flat.keys())
        placeholders = ", ".join("?" * len(cols))
        col_sql = ", ".join(f'"{c}"' for c in cols)
        try:
            conn.execute(
                f'INSERT INTO "{table}" ({col_sql}) VALUES ({placeholders})',
                list(flat.values()),
            )
            inserted += 1
        except Exception as exc:
            log.warning("Row insert failure in '%s': %s", table, exc)
    conn.commit()
    return inserted


# ---------------------------------------------------------------------------
# Main processing
# ---------------------------------------------------------------------------

def _process_file(
    path: Path,
    conn: sqlite3.Connection,
    fp_to_tbl: dict[str, str],
    tbl_to_fp: dict[str, str],
) -> str | None:
    """Process one file. Returns table name on success, None on skip/error."""
    file_key = str(path.resolve())

    if _already_imported(conn, file_key):
        log.info("SKIP (already imported): %s", path)
        return None

    # --- Parse ---
    try:
        if path.suffix == ".json":
            records = _parse_json(path)
        else:
            records = _parse_yaml(path)
    except (json.JSONDecodeError, yaml.YAMLError) as exc:
        log.warning("SKIP %s — %s", path, exc)
        return None
    except ValueError as exc:
        log.warning("SKIP %s — %s", path, exc)
        return None

    if not records:
        log.info("SKIP (empty): %s", path)
        return None

    # --- Schema → table name ---
    fp = _schema_fingerprint(records)
    if fp in fp_to_tbl:
        table = fp_to_tbl[fp]
    else:
        base = _sanitise_stem(path.stem)
        table = _unique_name(base, set(tbl_to_fp.keys()))
        fp_to_tbl[fp] = table
        tbl_to_fp[table] = fp

    # --- DDL + insert ---
    _ensure_table(conn, table, records)
    n = _insert_records(conn, table, records)
    _mark_imported(conn, file_key, table)
    conn.commit()

    log.info("OK  %s → table '%s' (%d row(s))", path, table, n)
    return table


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import JSON/YAML files recursively into SQLite."
    )
    parser.add_argument("folder_path", help="Root directory to scan")
    parser.add_argument("db_path", help="SQLite database file (created if absent)")
    args = parser.parse_args()

    folder = Path(args.folder_path)
    if not folder.is_dir():
        print(f"ERROR: '{folder}' is not a directory", file=sys.stderr)
        sys.exit(1)

    files = sorted(
        p for p in folder.rglob("*")
        if p.suffix in {".json", ".yml", ".yaml"} and p.is_file()
    )

    if not files:
        log.warning("No JSON/YAML files found in '%s'", folder)
        return

    json_count = sum(1 for f in files if f.suffix == ".json")
    yaml_count = len(files) - json_count
    log.info(
        "Found %d file(s) (%d JSON, %d YAML). Connecting to '%s'…",
        len(files), json_count, yaml_count, args.db_path,
    )

    conn = sqlite3.connect(args.db_path)
    _setup_db(conn)

    fp_to_tbl, tbl_to_fp = _load_registry(conn)

    imported = 0
    tables_touched: set[str] = set()

    for path in files:
        try:
            tbl = _process_file(path, conn, fp_to_tbl, tbl_to_fp)
            if tbl is not None:
                imported += 1
                tables_touched.add(tbl)
        except Exception as exc:
            log.warning("Unexpected error processing %s: %s", path, exc)

    conn.close()
    log.info(
        "Done. %d file(s) imported, %d table(s) created/updated: %s",
        imported, len(tables_touched), sorted(tables_touched),
    )


if __name__ == "__main__":
    main()
