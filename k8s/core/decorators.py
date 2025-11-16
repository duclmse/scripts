"""Command registration decorator"""

import argparse


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
    def register(cls, name: str, help: str, args: list | None = None, aliases: list[str] | None = None):
        """Decorator to register command"""
        def decorator(plugin_cls):
            if cls.cmd_parser is None:
                cls.init_parser()

            # Add parser for this command
            _aliases = aliases or []
            parser = cls.cmd_parser.add_parser(  # type: ignore
                name, aliases=_aliases, help=help)

            # Add arguments
            if args:
                for add_arg in args:
                    add_arg(parser)

            # Register plugin
            for alias in [name] + (_aliases):
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
        return cls.parser.parse_args()  # type: ignore
