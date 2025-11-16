"""Command registration decorator"""
import argparse


def arg(*args, **kwargs):
    """Helper to create argument adder"""
    def add_arg(parser: argparse.ArgumentParser):
        return parser.add_argument(*args, **kwargs)
    return add_arg


class Command:
    """Command registry and parser"""
    _plugins: dict[str, dict] = {}

    @classmethod
    def register(cls, name: str, help: str, args: list | None = None, aliases: list[str] | None = None):
        """Decorator to register command"""
        def decorator(plugin_cls):
            cls._plugins[name] = {
                'class': plugin_cls,
                'help': help,
                'args': args or [],
                'aliases': aliases or []
            }

            for alias in (aliases or []):
                cls._plugins[alias] = cls._plugins[name]

            return plugin_cls
        return decorator

    @classmethod
    def get_all_commands(cls):
        """Get all registered commands"""
        # Return unique commands (skip aliases)
        seen = set()
        commands = {}

        for name, metadata in cls._plugins.items():
            cmd_class = metadata['class']
            if cmd_class not in seen:
                seen.add(cmd_class)
                commands[name] = metadata
            # commands[name] = metadata

        return commands

    @classmethod
    def get_command(cls, name: str):
        """Get command class by name"""
        if name in cls._plugins:
            return cls._plugins[name]['class']
        return None
