#!/usr/bin/env python3

"""
Advanced Kubernetes Resource Manager
Version: 2.0.0
"""

import argparse
import json
import os
import re
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

# Configuration
CONFIG_DIR = Path.home() / ".kube-mgr"
FORWARDS_DB = CONFIG_DIR / "forwards.db"
CONFIG_FILE = CONFIG_DIR / "config.json"
BOOKMARKS_FILE = CONFIG_DIR / "bookmarks.json"

# Color codes


class Colors:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    BOLD = '\033[1m'
    RESET = '\033[0m'

    @classmethod
    def disable(cls):
        cls.RED = cls.GREEN = cls.YELLOW = cls.BLUE = ''
        cls.MAGENTA = cls.CYAN = cls.BOLD = cls.RESET = ''


# Check if output is TTY
if not sys.stdout.isatty():
    Colors.disable()


class Logger:
    """Logging utilities"""

    verbose = False

    @classmethod
    def info(cls, msg: str):
        print(f"{Colors.BLUE}ℹ{Colors.RESET} {msg}", file=sys.stderr)

    @classmethod
    def success(cls, msg: str):
        print(f"{Colors.GREEN}✓ {msg}{Colors.RESET}", file=sys.stderr)

    @classmethod
    def warn(cls, msg: str):
        print(f"{Colors.YELLOW}⚠{Colors.RESET} {msg}", file=sys.stderr)

    @classmethod
    def error(cls, msg: str):
        print(f"{Colors.RED}✗{Colors.RESET} {msg}", file=sys.stderr)

    @classmethod
    def verbose_log(cls, msg: str):
        if cls.verbose:
            print(
                f"{Colors.CYAN}[VERBOSE]{Colors.RESET} {msg}", file=sys.stderr)


def arg(*args: str, **kwargs):
    def add_arg(parser):
        return parser.add_argument(*args, **kwargs)
    return add_arg


def create_parser():
    """Create argument parser"""
    parser = argparse.ArgumentParser(
        description="Advanced Kubernetes Resource Manager",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    %(prog)s logs my-pod --follow
    %(prog)s exec -a backend -- ls -la
    %(prog)s port-forward start my-pod 8080:80
    %(prog)s scale my-deployment --replicas=3
    %(prog)s context bookmark add prod prod-cluster production

For more information on a subcommand:
    %(prog)s <subcommand> --help
        """
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

    cmd_parser = parser.add_subparsers(
        dest="command", help="Available commands")
    return parser, cmd_parser


class Command:
    _plugins: dict[str, type] = {}
    parser, cmd_parser = create_parser()

    @classmethod
    def register(cls, name: str, help: str, args: list, aliases: list[str] | None = None):
        """Decorator with plugin metadata"""
        def decorator(plugin_cls):
            cls.handle_params(name, aliases, help, args)
            cls.add_cmd(plugin_cls, ([name]+(aliases or [])))
            return plugin_cls
        return decorator

    @classmethod
    def handle_params(cls, name: str, alias: list[str] | None, help: str, args: list):
        parser = cls.cmd_parser.add_parser(
            name, aliases=alias or [], help=help)
        for add_arg in args:
            add_arg(parser)

    @classmethod
    def add_cmd(cls, plugin_cls: type, alias: list[str]):
        for n in alias:
            if n in cls._plugins:
                Logger.error(
                    f"duplicate cmd '{n}' in {cls._plugins[n]} and {plugin_cls}")
                exit(1)
            cls._plugins[n] = plugin_cls

    @classmethod
    def get_command(cls, cmd: str):
        return cls._plugins[cmd]


class KubeConfig:
    """Kubernetes configuration management"""

    def __init__(self):
        self.ensure_config_dir()

    @staticmethod
    def ensure_config_dir():
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        if not FORWARDS_DB.exists():
            FORWARDS_DB.write_text("[]")
        if not CONFIG_FILE.exists():
            CONFIG_FILE.write_text("{}")
        if not BOOKMARKS_FILE.exists():
            BOOKMARKS_FILE.write_text("{}")

    @staticmethod
    def load_json(filepath: Path) -> Any:
        try:
            return json.loads(filepath.read_text())
        except Exception as e:
            Logger.error(f"{e}")
            return {}

    @staticmethod
    def save_json(filepath: Path, data: Any):
        """Save JSON data to file"""
        filepath.write_text(json.dumps(data, indent=2))

    def get_forwards(self) -> list:
        """Get port forward entries"""
        return self.load_json(FORWARDS_DB)

    def save_forwards(self, forwards: list):
        """Save port forward entries"""
        self.save_json(FORWARDS_DB, forwards)

    def get_bookmarks(self) -> dict:
        """Get context bookmarks"""
        return self.load_json(BOOKMARKS_FILE)

    def save_bookmarks(self, bookmarks: dict):
        """Save context bookmarks"""
        self.save_json(BOOKMARKS_FILE, bookmarks)

    def get_config(self) -> dict:
        """Get general configuration"""
        return self.load_json(CONFIG_FILE)

    def save_config(self, config: dict):
        """Save general configuration"""
        self.save_json(CONFIG_FILE, config)


class KubeCommand:
    """Execute kubectl commands"""

    def __init__(self, namespace: str = "default", context: str | None = None, verbose: bool = False):
        self.namespace = namespace
        self.context = context
        self.verbose = verbose
        Logger.verbose = verbose

    def run(self, cmd: list[str], capture_output: bool = True, check: bool = True) -> subprocess.CompletedProcess:
        """Run kubectl command"""
        full_cmd = ["kubectl"] + cmd

        if self.context:
            full_cmd.extend(["--context", self.context])

        Logger.verbose_log(f"Running: {' '.join(full_cmd)}")

        try:
            if capture_output:
                result = subprocess.run(
                    full_cmd, capture_output=True, text=True, check=check)
            else:
                result = subprocess.run(full_cmd, check=check)
            return result
        except subprocess.CalledProcessError as e:
            Logger.error(f"Command failed: {e}")
            if e.stderr:
                print(e.stderr, file=sys.stderr)
            sys.exit(1)

    def get_pod(self, app_label: str) -> str:
        """Get pod name by app label"""
        Logger.verbose_log(f"Getting pod with label app={app_label}")
        result = self.run([
            "get", "pod",
            "-n", self.namespace,
            "-l", f"app={app_label}",
            "-o", "jsonpath={.items[0].metadata.name}"
        ])

        pod = result.stdout.strip()
        if not pod:
            Logger.error(
                f"No pod found with label 'app={app_label}' in namespace '{self.namespace}'")
            sys.exit(1)

        return pod

    def get_pods(self, selector: str) -> list[str]:
        """Get multiple pods by selector"""
        result = self.run([
            "get", "pods",
            "-n", self.namespace,
            "-l", selector,
            "-o", "jsonpath={.items[*].metadata.name}"
        ])
        return result.stdout.split()

    @staticmethod
    def get_current_context() -> str:
        """Get current kubectl context"""
        try:
            result = subprocess.run(
                ["kubectl", "config", "current-context"],
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout.strip()
        except Exception as e:
            Logger.error(f"error: {e}")
            return "unknown"


def main():
    """Main entry point"""
    parser = Command.parser
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    # Disable colors if requested
    if args.no_color:
        Colors.disable()

    # Create KubeCommand instance
    kube = KubeCommand(
        namespace=args.namespace,
        context=args.context,
        verbose=args.verbose
    )

    try:
        # Get command handler
        command_class = Command.get_command(args.command)

        if not command_class:
            Logger.error(f"Unknown command: {args.command}")
            parser.print_help()
            sys.exit(1)

        # Execute command
        command_class(kube).execute(args)
    except KeyboardInterrupt:
        Logger.error("\n\nInterrupted by user")
        sys.exit(130)
    except Exception as e:
        Logger.error(f"Command failed: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
