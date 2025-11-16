"""CLI entrypoint for file_format: python -m file_format <input> <output>"""

import argparse
import sys
from pathlib import Path

from core.colors import Colors
from core.logger import Logger

import file_format.formats  # noqa: F401 — triggers all format registrations
from file_format.base import FileFormat, FormatRegistry
from file_format.processor import FlatFileProcessor


# ---------------------------------------------------------------------------
# Format detection
# ---------------------------------------------------------------------------

def _detect_format(path: str) -> type[FileFormat] | None:
    """Detect format by file extension, then fall back to content sniffing."""
    ext = Path(path).suffix.lower()
    cls = FormatRegistry.get_by_extension(ext)
    if cls is not None:
        return cls
    # Extension gave no match — try to sniff the file content
    if Path(path).exists():
        return _sniff_format(path)
    return None


def _sniff_format(path: str) -> type[FileFormat] | None:
    """
    Guess format from the first few bytes of a file.

    Heuristics (in priority order):
      JSON   — first non-whitespace char is '[' or '{'
      YAML   — starts with '---' or 'key: value' pattern
      TSV    — lines contain tabs but no commas
      CSV    — lines contain commas (or other consistent delimiter)
      fixed_width — lines have consistent length, no common delimiters
    """
    import csv as _csv

    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            head = f.read(4096)
    except OSError:
        return None

    stripped = head.lstrip()
    if not stripped:
        return None

    # JSON
    if stripped[0] in ("[", "{"):
        return FormatRegistry.get("json")

    lines = [ln for ln in head.splitlines() if ln.strip()]
    if not lines:
        return None

    # YAML
    if stripped.startswith("---") or (": " in lines[0] and not "," in lines[0]):
        return FormatRegistry.get("yaml")

    # TSV — tabs present, no commas
    if "\t" in lines[0] and "," not in lines[0]:
        return FormatRegistry.get("tsv")

    # CSV — try sniffer on first line
    try:
        dialect = _csv.Sniffer().sniff(lines[0])
        if dialect.delimiter in (",", ";", "|"):
            return FormatRegistry.get("csv")
    except _csv.Error:
        pass

    # Fixed-width — lines have consistent length (±2 chars) and no delimiter
    if len(lines) >= 2:
        lengths = [len(ln) for ln in lines[:10]]
        spread = max(lengths) - min(lengths)
        if spread <= 2:
            return FormatRegistry.get("fixed_width")

    return None


# ---------------------------------------------------------------------------
# Interactive output format picker
# ---------------------------------------------------------------------------

def _prompt_output_format(output_path: str) -> type[FileFormat]:
    """
    Interactively ask the user to choose the output format.
    Shown when the output path's extension is not recognisable.
    """
    formats = FormatRegistry.list_formats()
    print(
        f"\n{Colors.YELLOW}Cannot detect output format"
        f" from '{Path(output_path).suffix or '(no extension)'}'.{Colors.RESET}"
    )
    print(f"Select output format for: {Colors.BOLD}{output_path}{Colors.RESET}\n")
    for i, name in enumerate(formats, 1):
        cls = FormatRegistry.get(name)
        exts = ", ".join(cls.file_extensions) if cls and cls.file_extensions else "—"
        print(f"  {Colors.CYAN}{i}{Colors.RESET}. {name:<14} ({exts})")
    print()

    while True:
        try:
            raw = input("Choice [1-{}]: ".format(len(formats))).strip()
        except (EOFError, KeyboardInterrupt):
            print()
            sys.exit(0)

        # Accept number or format name
        if raw.isdigit():
            idx = int(raw) - 1
            if 0 <= idx < len(formats):
                chosen = FormatRegistry.get(formats[idx])
                print(f"Using {Colors.GREEN}{formats[idx]}{Colors.RESET}\n")
                return chosen
        elif raw.lower() in formats:
            chosen = FormatRegistry.get(raw.lower())
            print(f"Using {Colors.GREEN}{raw.lower()}{Colors.RESET}\n")
            return chosen

        print(f"  {Colors.RED}Invalid choice.{Colors.RESET} Enter a number (1–{len(formats)})"
              f" or a format name ({', '.join(formats)}).")


def _build_format(fmt_cls: type[FileFormat], args: argparse.Namespace) -> FileFormat:
    from file_format.formats.fixed_width import PositionText
    from file_format.formats.csv_format import CSVFormat
    from file_format.formats.sql_format import SQLFormat

    if fmt_cls is PositionText:
        if not args.field_names or not args.field_positions:
            Logger.error("--field-names and --field-positions are required for fixed_width format")
            sys.exit(1)
        return PositionText(args.field_names, args.field_positions)

    if issubclass(fmt_cls, CSVFormat):
        return fmt_cls(delimiter=args.delimiter or None)

    if fmt_cls is SQLFormat:
        return SQLFormat(
            table_name=args.table_name,
            include_create_table=not args.no_create_table,
            batch_size=args.batch_size,
        )

    return fmt_cls()


def main():
    fmt_list = ", ".join(FormatRegistry.list_formats())

    parser = argparse.ArgumentParser(
        prog="file_format",
        description="Convert between text file formats",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"Available formats: {fmt_list}",
    )
    parser.add_argument("input", help="Input file path")
    parser.add_argument("output", help="Output file path")
    parser.add_argument(
        "--input-format", "-if",
        metavar="FORMAT",
        help=f"Override input format detection. One of: {fmt_list}",
    )
    parser.add_argument(
        "--output-format", "-of",
        metavar="FORMAT",
        help=f"Override output format detection. One of: {fmt_list}",
    )
    # fixed-width options
    parser.add_argument("--field-names", metavar="NAMES",
                        help="Comma-separated field names (required for fixed_width input)")
    parser.add_argument("--field-positions", metavar="POSITIONS",
                        help="Comma-separated position ranges e.g. '1-8,9-12' (fixed_width input)")
    # csv/tsv options
    parser.add_argument("--delimiter", metavar="CHAR",
                        help="CSV/TSV delimiter override")
    # sql options
    parser.add_argument("--table-name", metavar="NAME", default="table",
                        help="SQL table name (default: table)")
    parser.add_argument("--no-create-table", action="store_true",
                        help="Omit CREATE TABLE statement from SQL output")
    parser.add_argument("--batch-size", type=int, default=100, metavar="N",
                        help="Rows per INSERT statement (default: 100)")
    # global
    parser.add_argument("--no-color", action="store_true", help="Disable colored output")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")

    args = parser.parse_args()

    if args.no_color:
        Colors.disable()

    # Resolve format classes
    in_cls = (
        FormatRegistry.get(args.input_format)
        if args.input_format
        else _detect_format(args.input)
    )
    out_cls = (
        FormatRegistry.get(args.output_format)
        if args.output_format
        else _detect_format(args.output)
    )

    if in_cls is None:
        ext = Path(args.input).suffix or "(no extension)"
        Logger.error(
            f"Cannot detect input format from '{ext}'. "
            f"Use --input-format. Available: {fmt_list}"
        )
        sys.exit(1)

    if out_cls is None:
        out_cls = _prompt_output_format(args.output)

    in_fmt = _build_format(in_cls, args)
    out_fmt = _build_format(out_cls, args)

    if args.verbose:
        Logger.info(f"Input:  {in_fmt.describe()}")
        Logger.info(f"Output: {out_fmt.describe()}")

    try:
        FlatFileProcessor(in_fmt, out_fmt).process_file(args.input, args.output)
    except FileNotFoundError as e:
        Logger.error(str(e))
        sys.exit(1)
    except Exception as e:
        Logger.error(f"Conversion failed: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)
