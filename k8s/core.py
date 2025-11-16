#!/usr/bin/env python3
"""
Kubernetes Manager - Modular Command Structure
Each command is in its own file for easy maintenance
"""

# ==================== PROJECT STRUCTURE ====================
"""
k8s-manager/
├── main.py                    # Entry point
├── core/
│   ├── __init__.py
│   ├── config.py             # KubeConfig class
│   ├── kubectl.py            # KubeCommand wrapper
│   ├── logger.py             # Logger utilities
│   ├── colors.py             # Color definitions
│   └── decorators.py         # Command decorator
├── commands/
│   ├── __init__.py
│   ├── logs.py               # Logs commands
│   ├── exec.py               # Exec command
│   ├── context.py            # Context management
│   ├── port_forward.py       # Port forwarding
│   ├── scale.py              # Scaling
│   ├── rollout.py            # Rollout management
│   ├── status.py             # Status checking
│   ├── delete.py             # Delete resources
│   ├── describe.py           # Describe resources
│   ├── top.py                # Resource usage
│   ├── events.py             # Events monitoring
│   ├── tree.py               # Dependency tree
│   ├── backup.py             # Backup/restore
│   ├── diff.py               # Diff resources
│   ├── watch.py              # Watch resources
│   ├── apply.py              # Apply manifests
│   ├── debug.py              # Debug pods
│   ├── list.py               # List resources
│   ├── get.py                # Quick get (new)
│   ├── shell_all.py          # Multi-shell tmux (new)
│   ├── history.py            # Resource history (new)
│   ├── logs_merge.py         # Log aggregation (new)
│   ├── cost.py               # Cost analysis (new)
│   ├── ports.py              # Port manager TUI (new)
│   ├── template.py           # Resource templates (new)
│   ├── deps.py               # Dependency graph (new)
│   ├── health.py             # Health dashboard (new)
│   ├── doctor.py             # Auto-diagnose (new)
│   ├── secrets.py            # Secrets manager (new)
│   ├── jobs.py               # Jobs/CronJobs (new)
│   ├── compare.py            # Compare envs (new)
│   ├── complete.py           # Shell completion (new)
│   ├── restart.py            # Smart restart (new)
│   ├── validate.py           # Manifest validator (new)
│   ├── size.py               # Resource analyzer (new)
│   ├── netdebug.py           # Network debugging (new)
│   ├── clone.py              # Clone resources (new)
│   ├── interactive.py        # Interactive TUI (new)
│   ├── fav.py                # Favorite commands (new)
│   ├── bulk.py               # Bulk operations (new)
│   ├── git_deploy.py         # Git integration (new)
│   ├── watch_alert.py        # Notifications (new)
│   └── snippet.py            # YAML snippets (new)
└── utils/
    ├── __init__.py
    ├── parsers.py            # Argument parsing helpers
    ├── formatters.py         # Output formatting
    └── validators.py         # Input validation
"""

# ==================== core/colors.py ====================
COLORS_PY = '''
"""Color definitions for terminal output"""

class Colors:
    RED = '\\033[91m'
    GREEN = '\\033[92m'
    YELLOW = '\\033[93m'
    BLUE = '\\033[94m'
    MAGENTA = '\\033[95m'
    CYAN = '\\033[96m'
    BOLD = '\\033[1m'
    RESET = '\\033[0m'

    @classmethod
    def disable(cls):
        """Disable all colors"""
        cls.RED = cls.GREEN = cls.YELLOW = cls.BLUE = ''
        cls.MAGENTA = cls.CYAN = cls.BOLD = cls.RESET = ''
'''

# ==================== core/logger.py ====================
LOGGER_PY = '''
"""Logging utilities"""
import sys
from .colors import Colors

class Logger:
    verbose = False

    @classmethod
    def info(cls, msg: str):
        print(f"{Colors.BLUE}ℹ{Colors.RESET} {msg}", file=sys.stderr)

    @classmethod
    def success(cls, msg: str):
        print(f"{Colors.GREEN}✓{Colors.RESET} {msg}", file=sys.stderr)

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

    @classmethod
    def debug(cls, msg: str):
        if cls.verbose:
            print(
                f"{Colors.MAGENTA}[DEBUG]{Colors.RESET} {msg}", file=sys.stderr)
'''

# ==================== core/config.py ====================
CONFIG_PY = '''
"""Configuration management"""
import json
from pathlib import Path
from typing import Any
from .logger import Logger

CONFIG_DIR = Path.home() / ".kube-mgr"
FORWARDS_DB = CONFIG_DIR / "forwards.db"
CONFIG_FILE = CONFIG_DIR / "config.json"
BOOKMARKS_FILE = CONFIG_DIR / "bookmarks.json"
TEMPLATES_FILE = CONFIG_DIR / "templates.json"
FAVORITES_FILE = CONFIG_DIR / "favorites.json"
HISTORY_DIR = CONFIG_DIR / "history"

class KubeConfig:
    """Kubernetes configuration management"""

    def __init__(self):
        self.ensure_config_dir()

    @staticmethod
    def ensure_config_dir():
        """Ensure configuration directory exists"""
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        HISTORY_DIR.mkdir(parents=True, exist_ok=True)

        for file, default in [
            (FORWARDS_DB, "[]"),
            (CONFIG_FILE, "{}"),
            (BOOKMARKS_FILE, "{}"),
            (TEMPLATES_FILE, "{}"),
            (FAVORITES_FILE, "{}")
        ]:
            if not file.exists():
                file.write_text(default)

    @staticmethod
    def load_json(filepath: Path) -> Any:
        try:
            return json.loads(filepath.read_text())
        except Exception as e:
            Logger.error(f"Failed to load {filepath}: {e}")
            return {} if filepath.suffix == ".json" else []

    @staticmethod
    def save_json(filepath: Path, data: Any):
        filepath.write_text(json.dumps(data, indent=2))

    def get_forwards(self) -> list:
        return self.load_json(FORWARDS_DB)

    def save_forwards(self, forwards: list):
        self.save_json(FORWARDS_DB, forwards)

    def get_bookmarks(self) -> dict:
        return self.load_json(BOOKMARKS_FILE)

    def save_bookmarks(self, bookmarks: dict):
        self.save_json(BOOKMARKS_FILE, bookmarks)

    def get_templates(self) -> dict:
        return self.load_json(TEMPLATES_FILE)

    def save_templates(self, templates: dict):
        self.save_json(TEMPLATES_FILE, templates)

    def get_favorites(self) -> dict:
        return self.load_json(FAVORITES_FILE)

    def save_favorites(self, favorites: dict):
        self.save_json(FAVORITES_FILE, favorites)
'''

# ==================== core/kubectl.py ====================
KUBECTL_PY = '''
"""Kubectl command wrapper"""
import subprocess
import sys
from typing import List, Optional
from .logger import Logger

class KubeCommand:
    """Execute kubectl commands"""

    def __init__(self, namespace: str = "default", context: Optional[str] = None, verbose: bool = False):
        self.namespace = namespace
        self.context = context
        self.verbose = verbose
        Logger.verbose = verbose

    def run(self, cmd: List[str], capture_output: bool = True, check: bool = True) -> subprocess.CompletedProcess:
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
            "get", "pod", "-n", self.namespace,
            "-l", f"app={app_label}",
            "-o", "jsonpath={.items[0].metadata.name}"
        ])

        pod = result.stdout.strip()
        if not pod:
            Logger.error(
                f"No pod found with label 'app={app_label}' in namespace '{self.namespace}'")
            sys.exit(1)
        return pod

    def get_pods(self, selector: str) -> List[str]:
        """Get multiple pods by selector"""
        result = self.run([
            "get", "pods", "-n", self.namespace,
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
                capture_output=True, text=True, check=True
            )
            return result.stdout.strip()
        except Exception:
            return "unknown"
'''

# ==================== core/decorators.py ====================
DECORATORS_PY = '''
"""Command registration decorator"""
import argparse
from typing import List, Optional, Callable

def arg(*args: str, **kwargs):
    """Helper to create argument adder"""
    def add_arg(parser):
        return parser.add_argument(*args, **kwargs)
    return add_arg

class Command:
    """Command registry and parser"""
    _plugins: dict[str, type] = {}
    parser = None
    cmd_parser = None

    @classmethod
    def init_parser(cls):
        """Initialize argument parser"""
        cls.parser = argparse.ArgumentParser(
            description="Advanced Kubernetes Resource Manager",
            formatter_class=argparse.RawDescriptionHelpFormatter
        )

        # Global options
        cls.parser.add_argument("-a", "--app", help="App label to filter pods")
        cls.parser.add_argument("-c", "--context", help="Kubernetes context")
        cls.parser.add_argument("-n", "--namespace",
                                default="default", help="Kubernetes namespace")
        cls.parser.add_argument("-o", "--output", default="wide",
                               choices=["text", "json", "yaml", "wide"], help="Output format")
        cls.parser.add_argument(
            "--no-color", action="store_true", help="Disable colored output")
        cls.parser.add_argument(
            "-v", "--verbose", action="store_true", help="Enable verbose output")

        cls.cmd_parser = cls.parser.add_subparsers(
            dest="command", help="Available commands")

    @classmethod
    def register(cls, name: str, help: str, args: List = None, aliases: List[str] = None):
        """Decorator to register command"""
        def decorator(plugin_cls):
            if cls.cmd_parser is None:
                cls.init_parser()

            # Add parser for this command
            parser = cls.cmd_parser.add_parser(
                name, aliases=aliases or [], help=help)

            # Add arguments
            if args:
                for add_arg in args:
                    add_arg(parser)

            # Register plugin
            for alias in [name] + (aliases or []):
                if alias in cls._plugins:
                    raise ValueError(f"Command '{alias}' already registered")
                cls._plugins[alias] = plugin_cls

            return plugin_cls
        return decorator

    @classmethod
    def get_command(cls, cmd: str):
        """Get command class by name"""
        return cls._plugins.get(cmd)

    @classmethod
    def parse_args(cls):
        """Parse command line arguments"""
        if cls.parser is None:
            cls.init_parser()
        return cls.parser.parse_args()
'''

# ==================== commands/__init__.py ====================
COMMANDS_INIT = '''
"""Import all command modules to register them"""

# Core commands
from . import logs
from . import exec
from . import context
from . import port_forward
from . import scale
from . import rollout
from . import status
from . import delete
from . import describe
from . import top
from . import events
from . import tree
from . import backup
from . import diff
from . import watch
from . import apply
from . import debug
from . import list

# New advanced commands
from . import get
from . import shell_all
from . import history
from . import logs_merge
from . import cost
from . import ports
from . import template
from . import deps
from . import health
from . import doctor
from . import secrets
from . import jobs
from . import compare
from . import complete
from . import restart
from . import validate
from . import size
from . import netdebug
from . import clone
from . import interactive
from . import fav
from . import bulk
from . import git_deploy
from . import watch_alert
from . import snippet

__all__ = [
    'logs', 'exec', 'context', 'port_forward', 'scale', 'rollout',
    'status', 'delete', 'describe', 'top', 'events', 'tree',
    'backup', 'diff', 'watch', 'apply', 'debug', 'list',
    'get', 'shell_all', 'history', 'logs_merge', 'cost',
    'ports', 'template', 'deps', 'health', 'doctor',
    'secrets', 'jobs', 'compare', 'complete', 'restart',
    'validate', 'size', 'netdebug', 'clone', 'interactive',
    'fav', 'bulk', 'git_deploy', 'watch_alert', 'snippet'
]
'''

# ==================== main.py ====================
MAIN_PY = '''
#!/usr/bin/env python3
"""
Kubernetes Manager - Main Entry Point
"""
import sys
from core.decorators import Command
from core.kubectl import KubeCommand
from core.logger import Logger
from core.colors import Colors

# Import all commands to register them
import commands

def main():
    """Main entry point"""
    # Parse arguments
    args = Command.parse_args()

    if not args.command:
        Command.parser.print_help()
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

    # Get command class
    command_class = Command.get_command(args.command)

    if not command_class:
        Logger.error(f"Unknown command: {args.command}")
        Command.parser.print_help()
        sys.exit(1)

    # Execute command
    try:
        command_instance = command_class(kube)
        command_instance.execute(args)
    except KeyboardInterrupt:
        print("\\n\\nInterrupted by user", file=sys.stderr)
        sys.exit(130)
    except Exception as e:
        Logger.error(f"Command failed: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
'''

# Print file structure guide
print("=" * 60)
print("KUBERNETES MANAGER - MODULAR STRUCTURE")
print("=" * 60)
print("\nProject structure created above.")
print("\nNext steps:")
print("1. Create the directory structure")
print("2. Copy each section into its respective file")
print("3. Implement each command in commands/ directory")
print("\nEach command file should follow this pattern:")
print("=" * 60)

l = [
    {"name": "core/colors.py", "content": COLORS_PY},
    {"name": "core/logger.py", "content": LOGGER_PY},
    {"name": "core/config.py", "content": CONFIG_PY},
    {"name": "core/kubectl.py", "content": KUBECTL_PY},
    {"name": "core/decorators.py", "content": DECORATORS_PY},
    {"name": "commands/__init__.py", "content": COMMANDS_INIT},
    {"name": "main.py", "content": MAIN_PY},
]
for file in l:
    with open(file['name'], 'w') as f:
        f.write(file["content"])
