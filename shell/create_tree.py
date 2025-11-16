#!/usr/bin/env python3
"""
Create a directory/file tree from a tree-format or flat-path text file,
and convert between the two formats.

TREE FORMAT  — output of the `tree` command:
    ├── src/          # application source
    │   ├── main.py   # entry point
    │   └── utils/
    │       └── helpers.py
    └── README.md

FLAT FORMAT  — one path per line, directories end with /:
    README.md
    src/
    src/main.py
    src/utils/
    src/utils/helpers.py

Lines starting with '#' (after any leading whitespace) are treated as
comments and are ignored.  Inline comments after an item name are also
stripped.

The input format is auto-detected unless you specify --tree or --flat.

Usage:
    create_tree.py <file>                   # create filesystem from file
    create_tree.py -f <file> -r <root-dir>  # create under a specific root
    create_tree.py -f <file> --debug        # dry run, print paths only
    create_tree.py                          # interactive stdin mode
    create_tree.py -f <file> --to-flat      # convert tree → flat (stdout)
    create_tree.py -f <file> --to-tree      # convert flat → tree (stdout)
"""

import argparse
import re
import sys
from pathlib import Path, PurePosixPath

# ── tree-format parsing ────────────────────────────────────────────────────
# Group 1: tree-drawing prefix (box chars, pipes, dashes, spaces)
# Group 2: item name  (non-space, non-greedy)
# Group 3: trailing slash present → it's a directory
# Group 4: optional inline comment
_LINE_RE = re.compile(r'^([^\w]+)(\S+?)(/?)((\s*#.*)?)$')

# Each tree-indent level is 4 characters wide (e.g. "│   " or "├── " or "└── ")
_INDENT_WIDTH = 4

# Characters that appear in tree-format lines
_TREE_CHARS = frozenset('│├└─')


# ── format detection ───────────────────────────────────────────────────────

def detect_format(lines: list[str]) -> str:
    """Return 'tree' if lines contain tree-drawing characters, else 'flat'."""
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith('#'):
            continue
        if _TREE_CHARS & set(line):
            return 'tree'
    return 'flat'


# ── parsers ────────────────────────────────────────────────────────────────

def _strip_comment(text: str) -> str:
    """Remove a trailing inline comment (# …) from a path token."""
    idx = text.find('#')
    return text[:idx].rstrip() if idx != -1 else text


def parse_tree(lines: list[str]) -> list[tuple[str, bool]]:
    """Parse tree-format lines into (relative_path, is_dir) pairs."""
    stack: list[str] = []
    current_depth = 0
    paths: list[tuple[str, bool]] = []

    for raw_line in lines:
        stripped = raw_line.strip()
        if not stripped or stripped.startswith('#'):
            continue

        m = _LINE_RE.match(raw_line)
        if not m:
            continue

        indent = m.group(1)
        name   = m.group(2)
        is_dir = bool(m.group(3))

        if not name:
            continue

        depth = len(indent) // _INDENT_WIDTH

        while stack and depth <= current_depth:
            stack.pop()
            current_depth -= 1

        if is_dir:
            stack.append(name)
            current_depth = depth
            paths.append((str(PurePosixPath(*stack)), True))
        else:
            parent_parts = list(stack)
            rel = str(PurePosixPath(*parent_parts, name)) if parent_parts else name
            paths.append((rel, False))

    return paths


def parse_flat(lines: list[str]) -> list[tuple[str, bool]]:
    """Parse flat-format lines into (relative_path, is_dir) pairs."""
    paths: list[tuple[str, bool]] = []

    for raw_line in lines:
        stripped = raw_line.strip()
        if not stripped or stripped.startswith('#'):
            continue

        # strip inline comment
        entry = _strip_comment(stripped)
        if not entry:
            continue

        is_dir = entry.endswith('/')
        rel = entry.rstrip('/')
        if rel:
            paths.append((rel, is_dir))

    return paths


# ── renderers ─────────────────────────────────────────────────────────────

def render_flat(paths: list[tuple[str, bool]]) -> list[str]:
    """Convert (relative_path, is_dir) pairs to sorted flat-format lines."""
    out: list[str] = []
    for rel, is_dir in sorted(paths):
        out.append(rel + ('/' if is_dir else ''))
    return out


def _build_nodes(paths: list[tuple[str, bool]]) -> dict:
    """Build a nested dict representing the tree structure.

    Each node is a dict mapping child name → (is_dir, children_dict).
    """
    root: dict = {}

    for rel, is_dir in paths:
        parts = PurePosixPath(rel).parts
        node = root
        for i, part in enumerate(parts):
            is_last = i == len(parts) - 1
            if part not in node:
                node[part] = (is_last and is_dir, {})
            elif is_last and is_dir:
                # upgrade to directory if needed
                node[part] = (True, node[part][1])
            node = node[part][1]

    return root


def _render_nodes(nodes: dict, prefix: str = '') -> list[str]:
    """Recursively render a node dict into tree-format lines."""
    lines: list[str] = []
    items = sorted(nodes.items())
    for idx, (name, (is_dir, children)) in enumerate(items):
        is_last = idx == len(items) - 1
        connector = '└── ' if is_last else '├── '
        lines.append(prefix + connector + name + ('/' if is_dir else ''))
        if children:
            extension = '    ' if is_last else '│   '
            lines.extend(_render_nodes(children, prefix + extension))
    return lines


def render_tree(paths: list[tuple[str, bool]]) -> list[str]:
    """Convert (relative_path, is_dir) pairs to tree-format lines."""
    nodes = _build_nodes(paths)
    return _render_nodes(nodes)


# ── filesystem creator ─────────────────────────────────────────────────────

def create_from_paths(paths: list[tuple[str, bool]], root: Path, debug: bool) -> None:
    """Create directories and files on disk from (relative_path, is_dir) pairs."""
    for rel, is_dir in paths:
        full_path = root / rel
        if is_dir:
            print(f'> {full_path}/', file=sys.stderr)
            if not debug:
                full_path.mkdir(parents=True, exist_ok=True)
        else:
            print(f'> {full_path}', file=sys.stderr)
            if not debug:
                full_path.parent.mkdir(parents=True, exist_ok=True)
                full_path.touch()
    print('Done.', file=sys.stderr)


# ── CLI ────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='Create or convert a file/directory tree',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument('tree_file', nargs='?', metavar='FILE',
                        help='Input file (omit for interactive mode)')
    parser.add_argument('-f', '--file', dest='tree_file', metavar='FILE',
                        help='Input file (flag form)')
    parser.add_argument('-r', '--root', default='.',
                        help='Root directory to create the tree in (default: .)')
    parser.add_argument('-d', '--debug', action='store_true',
                        help='Dry run — print paths without creating anything')

    fmt_group = parser.add_argument_group('input format (auto-detected if omitted)')
    fmt_ex = fmt_group.add_mutually_exclusive_group()
    fmt_ex.add_argument('--tree', action='store_true',
                        help='Force tree-format input')
    fmt_ex.add_argument('--flat', action='store_true',
                        help='Force flat-format input')

    conv_group = parser.add_argument_group('format conversion (prints to stdout, no files created)')
    conv_ex = conv_group.add_mutually_exclusive_group()
    conv_ex.add_argument('--to-flat', action='store_true',
                         help='Convert input to flat format and print')
    conv_ex.add_argument('--to-tree', action='store_true',
                         help='Convert input to tree format and print')

    args = parser.parse_args()

    if args.tree_file:
        tree_path = Path(args.tree_file)
        if not tree_path.is_file():
            parser.error(f"file '{tree_path}' not found")

    return args


def read_interactive() -> list[str]:
    """Prompt the user to type a tree or flat structure, return the collected lines."""
    print('Tree format example:', file=sys.stderr)
    print('    ├── src/      # source dir', file=sys.stderr)
    print('    │   └── main.py', file=sys.stderr)
    print('    └── README.md', file=sys.stderr)
    print('Flat format example:', file=sys.stderr)
    print('    src/', file=sys.stderr)
    print('    src/main.py', file=sys.stderr)
    print('    README.md', file=sys.stderr)
    print('Enter tree or flat structure (Ctrl+D to finish):', file=sys.stderr)
    print(file=sys.stderr)

    lines: list[str] = []
    try:
        while True:
            line = input()
            lines.append(line)
    except EOFError:
        pass
    except KeyboardInterrupt:
        print('\nCancelled.', file=sys.stderr)
        sys.exit(0)

    return lines


def main():
    args = parse_args()

    if args.tree_file:
        lines = Path(args.tree_file).read_text().splitlines()
    else:
        lines = read_interactive()

    # Determine input format
    if args.tree:
        fmt = 'tree'
    elif args.flat:
        fmt = 'flat'
    else:
        fmt = detect_format(lines)

    # Parse into canonical (relative_path, is_dir) list
    paths = parse_tree(lines) if fmt == 'tree' else parse_flat(lines)

    # Conversion mode: print to stdout and exit
    if args.to_flat:
        print('\n'.join(render_flat(paths)))
        return
    if args.to_tree:
        print('\n'.join(render_tree(paths)))
        return

    # Default: create filesystem
    create_from_paths(paths, root=Path(args.root), debug=args.debug)


if __name__ == '__main__':
    main()
