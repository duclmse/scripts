"""Re-usable argparse helpers and command registry for CLI plugin system."""
from __future__ import annotations

import argparse
import functools
import os
from typing import Callable


def arg(*args, **kwargs) -> Callable[..., argparse.Action]:
    """Create an argument adder for use in command registrations.

    Supports an optional ``envvar`` keyword: if the named environment variable
    is set its value is used as the default.
    """
    envvar = kwargs.pop("envvar", None)

    def add_arg(parser: argparse.ArgumentParser) -> argparse.Action:
        kw = dict(kwargs)
        if envvar is not None:
            val = os.environ.get(envvar)
            if val is not None:
                t = kw.get("type")
                kw["default"] = t(val) if t is not None else val
        return parser.add_argument(*args, **kw)
    return add_arg


def flag(*args, **kwargs) -> Callable[..., argparse.Action]:
    """Shorthand for a boolean flag (``action="store_true"``)."""
    kwargs["action"] = "store_true"
    kwargs.setdefault("default", False)
    return arg(*args, **kwargs)


def choice(name: str, values: list[str], **kwargs) -> Callable[..., argparse.Action]:
    """Shorthand for an argument restricted to a fixed set of values."""
    kwargs["choices"] = list(values)
    kwargs.setdefault("metavar", "{" + "|".join(values) + "}")
    return arg(name, **kwargs)


def _wrap(plugin):
    """Wrap a plain ``fn(app, args)`` function in a class with ``execute()``."""
    if callable(plugin) and not isinstance(plugin, type):
        fn = plugin

        class _Wrapper:
            def __init__(self, context):
                self.context = context

            def execute(self, parsed_args):
                return fn(self.context, parsed_args)

        _Wrapper.__name__ = fn.__name__
        return _Wrapper
    return plugin


def mutating(destructive: bool = False) -> Callable:
    """Gate a mutating command behind dry-run / confirmation checks.

    Apply below other decorators so it wraps the raw ``(app, args)`` function::

        @group.register("delete", help="...", args=[...])
        @mutating(destructive=True)
        def delete(app, args): ...
    """
    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        def wrapper(app, args):
            app.guard(fn.__name__, destructive=destructive)
            return fn(app, args)
        return wrapper
    return decorator


class CommandGroup:
    """A named group of related sub-commands."""

    def __init__(self, name: str, help: str = "", aliases: list[str] | None = None) -> None:
        self.name = name
        self.help = help
        self.aliases = aliases or []
        self._entries: list[dict] = []
        self._subgroups: dict[str, "CommandGroup"] = {}

    def group(self, name: str, help: str = "", aliases: list[str] | None = None) -> "CommandGroup":
        """Create (or retrieve) a nested sub-group."""
        if name not in self._subgroups:
            qualified = f"{self.name}:{name}"
            self._subgroups[name] = CommandGroup(qualified, help, aliases)
        return self._subgroups[name]

    def register(
        self,
        name: str,
        help: str,
        args: list | None = None,
        aliases: list[str] | None = None,
    ):
        """Decorator to register a sub-command within this group."""
        def decorator(plugin):
            cmd_class = _wrap(plugin)
            key = f"{self.name}:{name}"
            entry = {
                "name": name,
                "class": cmd_class,
                "help": help,
                "args": args or [],
                "aliases": aliases or [],
            }
            self._entries.append(entry)
            Command._plugins[key] = entry
            for alias in (aliases or []):
                Command._plugins[f"{self.name}:{alias}"] = entry
            return plugin

        return decorator

    def _attach(self, group_parser: argparse.ArgumentParser) -> None:
        """Recursively attach all entries and nested sub-groups as subparsers."""
        subparsers = group_parser.add_subparsers(dest="subcommand")
        for entry in self._entries:
            key = f"{self.name}:{entry['name']}"
            sub = subparsers.add_parser(
                entry["name"], aliases=entry["aliases"], help=entry["help"]
            )
            sub.set_defaults(_command_key=key)
            for arg_adder in entry["args"]:
                arg_adder(sub)
        for sg_name, sg in self._subgroups.items():
            sg_parser = subparsers.add_parser(sg_name, aliases=sg.aliases, help=sg.help)
            sg._attach(sg_parser)


class Command:
    """Plugin registry and parser builder."""

    _plugins: dict[str, dict] = {}
    _groups: dict[str, CommandGroup] = {}

    @classmethod
    def register(
        cls,
        name: str,
        help: str,
        args: list | None = None,
        aliases: list[str] | None = None,
    ):
        """Decorator to register a flat (top-level) command."""
        def decorator(plugin):
            cmd_class = _wrap(plugin)
            entry = {
                "class": cmd_class,
                "help": help,
                "args": args or [],
                "aliases": aliases or [],
            }
            cls._plugins[name] = entry
            for alias in (aliases or []):
                cls._plugins[alias] = entry
            return plugin
        return decorator

    @classmethod
    def group(cls, name: str, help: str = "", aliases: list[str] = []) -> CommandGroup:
        """Create (or retrieve) a named top-level command group."""
        if name not in cls._groups:
            cls._groups[name] = CommandGroup(name, help, aliases)
        return cls._groups[name]

    @classmethod
    def build_parser(cls, parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
        """Attach all registered commands and groups as subparsers."""
        subparsers = parser.add_subparsers(dest="command")

        # Flat (non-group) commands — skip group:subcmd entries.
        for name, meta in cls._plugins.items():
            if ":" in name:
                continue
            sub = subparsers.add_parser(name, aliases=meta["aliases"], help=meta["help"])
            sub.set_defaults(_command_key=name)
            for arg_adder in meta["args"]:
                arg_adder(sub)

        # Top-level groups (with recursive nesting via _attach).
        for grp in cls._groups.values():
            grp_parser = subparsers.add_parser(grp.name, aliases=grp.aliases, help=grp.help)
            grp._attach(grp_parser)

        return parser

    @classmethod
    def resolve(cls, args: argparse.Namespace):
        """Return the command class to invoke, or None if no command matched."""
        key = getattr(args, "_command_key", None)
        if key is None:
            return None
        return cls.get_command(key)

    @classmethod
    def get_command(cls, name: str):
        """Get command class by name (supports ``group:subcmd`` keys)."""
        entry = cls._plugins.get(name)
        return entry["class"] if entry else None
