"""
Auto-discover and import all command modules in this package so that each
module's @Command.register() decorator fires and registers the command.

Drop a new .py file here (with a @Command.register() class) and it is
picked up automatically — no manual import needed.
"""

import argparse
import importlib
import pkgutil
from pathlib import Path

from .kubectl import KubeCommand

_SKIP = {"__init__", "kubectl"}

for _mod_info in pkgutil.iter_modules([str(Path(__file__).parent)]):
    if _mod_info.name not in _SKIP:
        importlib.import_module(f".{_mod_info.name}", package=__name__)


def init_parser():
    """Initialize argument parser"""
    parser = argparse.ArgumentParser(
        description="Advanced Kubernetes Resource Manager",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    # Global options
    parser.add_argument("-a", "--app", help="App label to filter pods")
    parser.add_argument("-c", "--context", help="Kubernetes context")
    parser.add_argument(
        "-n", "--namespace", default="default", help="Kubernetes namespace")
    parser.add_argument(
        "-o", "--output", default="wide", choices=["text", "json", "yaml", "wide"], help="Output format")
    parser.add_argument(
        "--no-color", action="store_true", help="Disable colored output")
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable verbose output")

    return parser


def register_commands(parser: argparse.ArgumentParser, commands: dict[str, dict]):
    """Register all commands to the parser"""
    subparser = parser.add_subparsers(
        dest="command", help="Available commands")

    for name, metadata in commands.items():
        # Create subparser for this command
        cmd_parser = subparser.add_parser(
            name,
            aliases=metadata['aliases'],
            help=metadata['help']
        )

        # Add command-specific arguments
        for arg_adder in metadata['args']:
            arg_adder(cmd_parser)
    return parser


__all__ = ['KubeCommand', 'init_parser', 'register_commands']
