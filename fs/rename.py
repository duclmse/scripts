#!/usr/bin/env python3
import re
from pathlib import Path


def batch_rename_regex(
    folder: Path,
    pattern: str,
    replacement: str,
    dry_run: bool = True,
):
    """
    Batch rename files in a folder using a regex pattern.

    Args:
        folder: Directory containing files to rename.
        pattern: Regex pattern to match filenames.
        replacement: Replacement pattern (supports backrefs like \\1, \\g<1>).
        dry_run: If True, only print what will be renamed.
    """
    if not folder.is_dir():
        print(f"❌ '{folder}' is not a directory.")
        return

    regex = re.compile(pattern)

    renamed = 0
    for f in sorted(folder.iterdir()):
        if not f.is_file():
            continue

        match = regex.search(f.name)
        if not match:
            continue

        new_name = regex.sub(replacement, f.name)
        new_path = f.with_name(new_name)

        if new_path.exists():
            print(f"⚠️ Skipping (target exists): {new_name}")
            continue

        if dry_run:
            print(f"🟡 Would rename: {f.name} → {new_name}")
        else:
            print(f"✅ Renamed: {f.name} → {new_name}")
            f.rename(new_path)
        renamed += 1

    if renamed == 0:
        print("ℹ️ No files matched the pattern.")
    elif dry_run:
        print(f"\n💡 Use --apply to actually rename ({renamed} matches found).")
    else:
        print(f"\n✅ Renamed {renamed} file(s).")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Batch rename files using regex.")
    parser.add_argument("folder", type=str, help="Path to folder")
    parser.add_argument("pattern", type=str, help="Regex pattern to match")
    parser.add_argument(
        "replacement", type=str, help="Replacement (supports backrefs like \\1)"
    )
    parser.add_argument(
        "--apply", action="store_true", help="Actually rename (default: dry run)"
    )

    args = parser.parse_args()

    batch_rename_regex(
        Path(args.folder),
        args.pattern,
        args.replacement,
        dry_run=not args.apply,
    )
