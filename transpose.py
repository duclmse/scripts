#!/usr/bin/env python3

import sys
import re

def is_table_line(line: str) -> bool:
    return "|" in line and not line.strip().startswith("```")

def is_separator_row(row):
    return all(re.match(r"^:?-+:?$", cell.strip()) for cell in row)

def parse_row(line: str):
    line = line.strip().strip("|")
    return [cell.strip() for cell in line.split("|")]

def format_row(row):
    return "| " + " | ".join(row) + " |"

def transpose_table(rows):
    max_cols = max(len(r) for r in rows)
    norm = [r + [""] * (max_cols - len(r)) for r in rows]
    return [list(r) for r in zip(*norm)]

def process_table(lines):
    rows = [parse_row(line) for line in lines]

    if len(rows) > 1 and is_separator_row(rows[1]):
        rows.pop(1)

    transposed = transpose_table(rows)

    separator = ["---"] * len(transposed[0])
    output = []

    for i, row in enumerate(transposed):
        output.append(format_row(row))
        if i == 0:
            output.append(format_row(separator))

    return output

def process_markdown(text):
    lines = text.splitlines()
    output = []

    buffer = []
    in_table = False
    in_code_block = False

    for line in lines:
        # handle code fences
        if line.strip().startswith("```"):
            in_code_block = not in_code_block
            output.append(line)
            continue

        if not in_code_block and is_table_line(line):
            buffer.append(line)
            in_table = True
        else:
            if in_table:
                output.extend(process_table(buffer))
                buffer = []
                in_table = False
            output.append(line)

    if buffer:
        output.extend(process_table(buffer))

    return "\n".join(output)

# ==============================
# INPUT HANDLING
# ==============================
def read_input():
    if len(sys.argv) > 1:
        # file mode
        with open(sys.argv[1], "r", encoding="utf-8") as f:
            return f.read()
    else:
        # stdin / paste mode
        if sys.stdin.isatty():
            print("Paste your markdown (Ctrl+D on Linux/macOS, Ctrl+Z then Enter on Windows):")

        return sys.stdin.read()

def main():
    content = read_input()

    if not content.strip():
        print("No input provided.", file=sys.stderr)
        sys.exit(1)

    result = process_markdown(content)
    print(result)

if __name__ == "__main__":
    main()