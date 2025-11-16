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
