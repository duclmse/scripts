# Prompt: Recursive JSON & YAML → SQLite Importer

## Task

Write a Python 3.10+ command-line script called `data_to_sqlite.py` that recursively scans a folder for **JSON** (`.json`) and **YAML** (`.yml`, `.yaml`) files and imports all their data into a **SQLite** database.

---

## CLI Interface

```
python data_to_sqlite.py <folder_path> <db_path>
```

- `folder_path` — root directory to scan recursively  
- `db_path` — SQLite database file to write to (created if it does not exist)

---

## File Discovery

- Recursively walk `folder_path` using `pathlib.Path.rglob`.
- Collect files matching extensions: `.json`, `.yml`, `.yaml`.
- Process files in sorted order for deterministic output.
- Log a warning and exit cleanly if no matching files are found.

---

## Parsing Rules

### JSON files
- Parse with the standard `json` module.
- Accept either a single JSON object `{}` or an array of objects `[{}, …]`.
- Raise/log a `ValueError` for any other shape (e.g. bare array of scalars, bare string).

### YAML files
- Parse with **`PyYAML`** (`import yaml`; use `yaml.safe_load`).
- Accept either a single mapping or a list of mappings — same shape rules as JSON.
- A YAML file may contain **multiple documents** separated by `---`; treat each document as a separate record (use `yaml.safe_load_all`).
- Raise/log a `ValueError` if any document is not a mapping.

### Shared parsing behaviour
- On parse error (malformed JSON or YAML), log a `WARNING` with the filename and error message, then **skip** that file — do not abort the whole run.
- On empty file or empty list of records, log `INFO` and skip.

---

## Flattening & Type Mapping

- Before inserting, **flatten** each record: any value that is a `dict` or `list` must be serialised to a JSON string (`json.dumps`) and stored in a `TEXT` column.
- Map Python types to SQLite column types:
  | Python type | SQLite type |
  |-------------|-------------|
  | `bool`      | `INTEGER`   |
  | `int`       | `INTEGER`   |
  | `float`     | `REAL`      |
  | everything else (`str`, `None`, serialised nested) | `TEXT` |
- Check `bool` **before** `int` (since `bool` is a subclass of `int` in Python).

---

## Schema Detection & Table Assignment

- A file's **schema** is defined as the **frozenset of all top-level keys** appearing across all its records.
- Compute a stable string fingerprint: `",".join(sorted(keys))`.
- Files that share the same fingerprint are inserted into the **same table**.
- When a new schema fingerprint is seen for the first time:
  - Derive the table name from the **filename stem** (first file with that schema).
  - Sanitise the stem: keep only alphanumerics, spaces, dashes, and underscores; lowercase; collapse runs of non-alphanumeric characters to a single `_`; strip leading/trailing `_`. Fall back to `"data"` if nothing usable remains.
  - If the sanitised name is already taken by a **different** schema, append `_1`, `_2`, etc. until unique.
- Table names must remain stable across re-runs (seed the name registry from `_imported_files` at startup).

---

## Dynamic Schema Evolution

- When inserting into an **existing** table, check `PRAGMA table_info` for current columns.
- For any column present in the new record but **absent** from the table, issue `ALTER TABLE … ADD COLUMN` before inserting.
- This means a table can grow columns over time without breaking existing rows (missing values become `NULL`).

---

## Idempotency — Skip Already-Imported Files

- Maintain a tracking table `_imported_files` in the same SQLite database:

  ```sql
  CREATE TABLE IF NOT EXISTS _imported_files (
      file_path  TEXT PRIMARY KEY,
      imported_at TEXT DEFAULT (datetime('now')),
      table_name  TEXT
  );
  ```

- At the start of each file, query `_imported_files` by the **absolute or consistent relative path string**.
- If the path is already present → log `INFO "SKIP (already imported): <path>"` and move on.
- After successfully inserting all rows from a file → insert a row into `_imported_files`.
- Use `INSERT OR IGNORE` so concurrent or repeated calls never raise a unique-constraint error.

---

## Database Setup

- Open the connection with `sqlite3.connect(db_path)`.
- Enable WAL mode: `conn.execute("PRAGMA journal_mode=WAL")`.
- Call `conn.commit()` after DDL changes and after each file's batch of inserts.

---

## Logging

Use Python's `logging` module (level `INFO` by default, format `"%(levelname)s  %(message)s"`).

| Event | Level |
|-------|-------|
| File skipped — already imported | `INFO` |
| File skipped — empty | `INFO` |
| File skipped — parse error | `WARNING` |
| File skipped — unsupported shape | `WARNING` |
| Table created | `INFO` |
| Column added to existing table | `INFO` |
| File successfully imported (`OK <path> → table '<name>' (<N> row(s))`) | `INFO` |
| Row insert failure | `WARNING` |
| Summary line at end | `INFO` |

---

## Error Handling

- Wrap each file's processing in a `try/except` so one bad file never aborts the run.
- If `folder_path` is not a directory, print an error and `sys.exit(1)`.

---

## Dependencies

- Standard library only: `argparse`, `json`, `logging`, `sqlite3`, `sys`, `pathlib`.
- Third-party: **`PyYAML`** (`pip install pyyaml`) for YAML parsing.
- No other third-party libraries.

---

## Example Output

```
INFO  Found 7 file(s) (5 JSON, 2 YAML). Connecting to 'output.db'…
INFO  Created table 'users' with columns: ['id', 'name', 'email']
INFO  OK  data/users.json → table 'users' (42 row(s))
INFO  SKIP (already imported): data/products.json
INFO  Created table 'orders' with columns: ['order_id', 'user_id', 'total']
INFO  OK  data/orders.yml → table 'orders' (18 row(s))
INFO  Added column 'discount' (REAL) to table 'orders'
INFO  OK  data/orders_v2.yaml → table 'orders' (5 row(s))
WARNING  SKIP data/corrupt.json — Expecting value: line 1 column 1 (char 0)
INFO  Done. 4 file(s) imported, 2 table(s) created/updated: ['users', 'orders']
```

---

## Constraints & Non-Goals

- Do **not** deduplicate rows within the same file or across files — insert all records as-is.
- Do **not** support nested table normalisation; store nested structures as serialised JSON text.
- Do **not** support CSV, TOML, or any other format — only `.json`, `.yml`, `.yaml`.
- The script is single-threaded; no concurrency required.
