"""CLI entrypoint for the Git Repository Manager"""

import argparse
import sys

from core.decorators import Command
from core.logger import Logger
from git.context import GitContext

# Import all commands to register them
import git.commands  # noqa: F401


def init_parser() -> argparse.ArgumentParser:
    """Build the argument parser with global flags only."""
    parser = argparse.ArgumentParser(
        prog="git",
        description="Git Repository Manager — Advanced multi-repository management tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Examples:
  %(prog)s clone --parallel 5 --skip-existing
  %(prog)s sync --interactive --retry 3
  %(prog)s backup --output backup.tar.gz
  %(prog)s import-github username --private
  %(prog)s discover ~/projects --output repos.txt
        """,
    )

    parser.add_argument("-V", "--version", action="version",
                        version=f"%(prog)s {GitContext.VERSION}")

    # Global flags (available to every command)
    parser.add_argument("-f", "--file", default="repos.txt",
                        help="Config file (default: repos.txt)")
    parser.add_argument("--log", help="Log to file")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show commands without executing")
    parser.add_argument("--parallel", type=int, default=1, metavar="N",
                        help="Process N repos simultaneously (default: 1)")
    parser.add_argument("--skip-existing", action="store_true",
                        help="Skip if local folder already exists")
    parser.add_argument("--force", action="store_true",
                        help="Force overwrite existing folders")
    parser.add_argument("--interactive", action="store_true",
                        help="Prompt before each operation")
    parser.add_argument("--retry", type=int, default=3, metavar="N",
                        help="Retry failed operations N times (default: 3)")
    parser.add_argument("--timeout", type=int, default=300, metavar="SEC",
                        help="Operation timeout in seconds (default: 300)")
    parser.add_argument("--include", metavar="PATTERN",
                        help="Only process repos matching regex pattern")
    parser.add_argument("--exclude", metavar="PATTERN",
                        help="Skip repos matching regex pattern")
    parser.add_argument("--ssh", action="store_true",
                        help="Convert HTTPS URLs to SSH")
    parser.add_argument("--submodules", action="store_true",
                        help="Include submodules recursively")
    parser.add_argument("--mirror", action="store_true",
                        help="Create mirror clones")
    parser.add_argument("--bare", action="store_true",
                        help="Create bare repositories")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Verbose output")

    return parser


def register_commands(parser: argparse.ArgumentParser, commands: dict):
    """Attach each registered command as a subparser."""
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    for name, meta in commands.items():
        sub = subparsers.add_parser(name, aliases=meta["aliases"], help=meta["help"])
        for arg_adder in meta["args"]:
            arg_adder(sub)
    return parser


def main():
    parser = init_parser()
    register_commands(parser, Command.get_all_commands())
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    context = GitContext(args)
    context.check_dependencies()

    command_class = Command.get_command(args.command)
    if not command_class:
        Logger.error(f"Unknown command: {args.command}")
        sys.exit(1)

    try:
        command_class(context).execute(args)
    except KeyboardInterrupt:
        Logger.warn("\nOperation cancelled by user")
        sys.exit(130)
    except Exception as e:
        Logger.error(f"Unexpected error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)
