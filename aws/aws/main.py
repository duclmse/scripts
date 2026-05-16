"""CLI entry point — root command group, global options, and built-in commands."""
from __future__ import annotations

import sys

from . import __version__
from .auth import Auth
from .cache import Cache
from .config import Config
from .context import AppContext
from .core.loader import LazyGroup
from .exceptions import AWSCLIError, DryRunAbort
from .logger import get_logger, set_level

log = get_logger("main")

_CONTEXT_SETTINGS = {
    "help_option_names": ["-h", "--help"],
    "max_content_width": 120,
    "auto_envvar_prefix": "AWS",
}



@click.option("--profile", envvar="AWS_PROFILE", help="AWS credential profile.")
@click.option("--region", "-r", envvar="AWS_DEFAULT_REGION", default=None,
              help="AWS region (overrides config and env).")
@click.option("--role", envvar="AWS_ROLE", default=None,
              help="IAM role ARN or config alias to assume.")
@click.option("--output", "-o",
              type=click.Choice(["table", "json", "yaml", "csv"], case_sensitive=False),
              default=None, help="Output format.")
@click.option("--dry-run", is_flag=True, envvar="AWS_DRY_RUN",
              help="Preview mutating operations without executing them.")
@click.option("--log-level",
              type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR"], case_sensitive=False),
              default=None, envvar="AWS_LOG_LEVEL", help="Logging verbosity.")
@click.option("--config", "config_path", type=click.Path(), envvar="AWS_CONFIG",
              help="Path to config file (default: auto-discovered).")
@click.option("--no-cache", is_flag=True, help="Bypass the response cache for this invocation.")
@click.option("--yes", "-y", is_flag=True, help="Auto-confirm destructive operations.")
@click.option("--verbose", "-v", is_flag=True, help="Print extra diagnostic information.")
@click.pass_context
def cli(
    ctx: click.Context,
    profile: str | None,
    region: str | None,
    role: str | None,
    output: str | None,
    dry_run: bool,
    log_level: str | None,
    config_path: str | None,
    no_cache: bool,
    yes: bool,
    verbose: bool,
) -> None:
    """AWS CLI utility — modular, cached, dry-run-aware boto3 wrapper.

    \b
    Examples:
      aws ec2 instances list --state running
      aws s3 objects ls s3://my-bucket/logs/ --recursive
      aws iam users list
      aws lambda functions invoke my-fn --payload '{"key": "val"}'
      aws cost usage --group-by SERVICE
      aws --dry-run ec2 instances terminate i-abc123
    """
    ctx.ensure_object(dict)

    cfg = Config(config_path)

    # Apply CLI overrides to config so everything downstream reads from one place.
    if log_level:
        cfg.set("log_level", log_level)
        set_level(log_level)
    elif cfg.get("log_level"):
        set_level(cfg.get("log_level", "INFO"))

    cache = Cache(
        cache_dir=None,
        default_ttl=int(cfg.get("cache_ttl", 300)),
    )
    auth = Auth(cfg, cache)

    app = AppContext(
        config=cfg,
        auth=auth,
        cache=cache,
        profile=profile or cfg.get("profile"),
        region=region or cfg.get("region", "us-east-1"),
        role=role or cfg.get("role"),
        output=output or cfg.get("output", "table"),
        dry_run=dry_run or bool(cfg.get("dry_run", False)),
        no_cache=no_cache or not bool(cfg.get("cache_enabled", True)),
        yes=yes,
        verbose=verbose,
    )
    ctx.obj = app

    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


# ── Built-in commands (not plugins) ───────────────────────────────────────────

@cli.command("whoami")
@click.pass_obj
def whoami(app: AppContext) -> None:
    """Show the current AWS caller identity."""
    identity = app.auth.whoami(
        profile=app.profile,
        region=app.region,
        role=app.role,
    )
    app.out({
        "UserId": identity["UserId"],
        "Account": identity["Account"],
        "Arn": identity["Arn"],
    })


@cli.group("cache")
@click.pass_obj
def cache_cmd(app: AppContext) -> None:
    """Manage the local response cache."""


@cache_cmd.command("stats")
@click.pass_obj
def cache_stats(app: AppContext) -> None:
    """Show cache statistics."""
    app.out(app.cache.stats())


@cache_cmd.command("clear")
@click.option("--prefix", default=None, help="Only clear entries whose key starts with PREFIX.")
@click.pass_obj
def cache_clear(app: AppContext, prefix: str | None) -> None:
    """Delete cached responses."""
    deleted = app.cache.clear(prefix=prefix)
    click.echo(f"Cleared {deleted} cache entry/entries.")


@cli.command("config-dump")
@click.pass_obj
def config_dump(app: AppContext) -> None:
    """Print the effective configuration (post env-var override)."""
    import json
    click.echo(json.dumps(app.config.as_dict(), indent=2, default=str))


# ── Error handling / entrypoint ───────────────────────────────────────────────

def main() -> None:  # pragma: no cover
    try:
        cli(standalone_mode=False, obj={})
    except DryRunAbort as exc:
        click.echo(click.style(f"[DRY RUN] Aborted: {exc}", fg="yellow"))
        sys.exit(0)
    except AWSCLIError as exc:
        click.echo(click.style(f"Error: {exc}", fg="red"), err=True)
        if exc.details:
            click.echo(click.style(f"  {exc.details}", fg="red"), err=True)
        sys.exit(exc.exit_code)
    except click.exceptions.Abort:
        click.echo("\nAborted.", err=True)
        sys.exit(1)
    except KeyboardInterrupt:
        click.echo("\nInterrupted.", err=True)
        sys.exit(130)
    except Exception as exc:
        log.exception("unhandled exception", extra={"err": str(exc)})
        click.echo(click.style(f"Unexpected error: {exc}", fg="red"), err=True)
        sys.exit(1)
