"""Tests for aws.core.decorators.mutating()."""
from __future__ import annotations

import click
import pytest
from click.testing import CliRunner

from aws.context import AppContext
from aws.core.decorators import mutating
from aws.exceptions import DryRunAbort
from aws.auth import Auth
from aws.cache import Cache
from aws.config import Config


def _make_app(dry_run: bool = False, yes: bool = True, tmp_path=None) -> AppContext:
    import tempfile, pathlib
    td = tmp_path or pathlib.Path(tempfile.mkdtemp())
    cfg = Config()
    cache = Cache(cache_dir=str(td))
    auth = Auth(cfg, cache)
    return AppContext(config=cfg, auth=auth, cache=cache, dry_run=dry_run, yes=yes)


def _build_cli(dry_run: bool, yes: bool, tmp_path):
    """Build a minimal CLI that exercises the @mutating decorator."""
    app = _make_app(dry_run=dry_run, yes=yes, tmp_path=tmp_path)

    @click.group()
    @click.pass_context
    def root(ctx):
        ctx.ensure_object(dict)
        ctx.obj = app

    @root.command("do-thing")
    @click.argument("name")
    @click.pass_obj
    @mutating()
    def do_thing(a: AppContext, name: str) -> None:
        click.echo(f"executed:{name}")

    @root.command("destroy-thing")
    @click.argument("name")
    @click.pass_obj
    @mutating(destructive=True)
    def destroy_thing(a: AppContext, name: str) -> None:
        click.echo(f"destroyed:{name}")

    return root


def test_mutating_executes_normally(tmp_path):
    root = _build_cli(dry_run=False, yes=True, tmp_path=tmp_path)
    result = CliRunner().invoke(root, ["do-thing", "foo"], catch_exceptions=False)
    assert result.exit_code == 0
    assert "executed:foo" in result.output


def test_mutating_dry_run_skips_body(tmp_path):
    root = _build_cli(dry_run=True, yes=True, tmp_path=tmp_path)
    result = CliRunner().invoke(root, ["do-thing", "foo"], catch_exceptions=False)
    assert "DRY RUN" in result.output
    assert "executed:foo" not in result.output


def test_mutating_dry_run_exit_code_zero(tmp_path):
    root = _build_cli(dry_run=True, yes=True, tmp_path=tmp_path)
    result = CliRunner().invoke(root, ["do-thing", "bar"])
    # DryRunAbort has exit_code=0; standalone_mode=True (default) calls sys.exit(0)
    assert result.exit_code == 0


def test_destructive_auto_confirmed_with_yes(tmp_path):
    root = _build_cli(dry_run=False, yes=True, tmp_path=tmp_path)
    result = CliRunner().invoke(root, ["destroy-thing", "prod"], catch_exceptions=False)
    assert "destroyed:prod" in result.output


def test_destructive_prompts_without_yes(tmp_path):
    root = _build_cli(dry_run=False, yes=False, tmp_path=tmp_path)
    # Supply "y\n" to the confirmation prompt.
    result = CliRunner().invoke(root, ["destroy-thing", "prod"], input="y\n", catch_exceptions=False)
    assert "destroyed:prod" in result.output


def test_destructive_abort_on_no(tmp_path):
    root = _build_cli(dry_run=False, yes=False, tmp_path=tmp_path)
    result = CliRunner().invoke(root, ["destroy-thing", "prod"], input="n\n")
    assert "destroyed:prod" not in result.output
    assert result.exit_code != 0
