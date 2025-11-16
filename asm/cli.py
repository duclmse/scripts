"""CLI entry point for the ARM64 assembler"""

import argparse
import os
import sys

from asm.assembler import ARM64Assembler
from asm.macho import write_macho


def main() -> None:
    parser = argparse.ArgumentParser(
        description='ARM64 assembler — produces native Mach-O executables for macOS ARM64',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Examples:
  %(prog)s hello.s -o hello
  %(prog)s hello.s -o hello -d
  %(prog)s hello.s -o hello -e main -b 0x100000000
""",
    )
    parser.add_argument('input', help='Assembly source file (.s)')
    parser.add_argument('-o', '--output', default='a.out', help='Output file (default: a.out)')
    parser.add_argument('-e', '--entry', default='_start', help='Entry-point label (default: _start)')
    parser.add_argument('-b', '--base', type=lambda x: int(x, 0), default=0x100000000,
                        metavar='ADDR', help='Base address (default: 0x100000000)')
    parser.add_argument('-d', '--disassemble', action='store_true',
                        help='Print hex dump of assembled output')

    args = parser.parse_args()

    try:
        with open(args.input) as f:
            source = f.read()
    except FileNotFoundError:
        print(f"Error: '{args.input}' not found", file=sys.stderr)
        sys.exit(1)

    try:
        asm = ARM64Assembler()
        machine_code = asm.assemble(source, args.base)
        print(f"Assembled {len(machine_code)} instructions")

        write_macho(args.output, machine_code, asm.labels, args.base, args.entry)
        os.chmod(args.output, 0o755)
        print(f"Run with: ./{args.output}")

        if args.disassemble:
            print("\nDisassembly:")
            print(asm.disassemble(args.base))

    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
