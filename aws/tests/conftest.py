"""Shared pytest fixtures for the aws test suite."""
from __future__ import annotations

import os
import tempfile
from typing import Generator

import boto3
import pytest
from click.testing import CliRunner
from moto import mock_aws

from aws.auth import Auth
from aws.cache import Cache
from aws.config import Config
from aws.context import AppContext
from aws.main import cli


# ── AWS credential stubs (moto requires these) ────────────────────────────────
@pytest.fixture(autouse=True)
def _aws_env(monkeypatch):
    """Inject fake AWS credentials so every test runs under moto without real creds."""
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_SECURITY_TOKEN", "testing")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")


# ── Moto mock ─────────────────────────────────────────────────────────────────
@pytest.fixture
def aws_mock():
    """Activate moto's multi-service mock for the duration of a test."""
    with mock_aws():
        yield


# ── Config / Cache / Auth / AppContext ────────────────────────────────────────
@pytest.fixture
def tmp_cache(tmp_path) -> Cache:
    return Cache(cache_dir=str(tmp_path / "cache"), default_ttl=300)


@pytest.fixture
def cfg() -> Config:
    """Minimal Config instance (no file, only defaults)."""
    return Config()


@pytest.fixture
def app(cfg, tmp_cache, aws_mock) -> AppContext:
    """Full AppContext wired to moto mocks."""
    auth = Auth(cfg, tmp_cache)
    return AppContext(
        config=cfg,
        auth=auth,
        cache=tmp_cache,
        region="us-east-1",
        output="json",
        dry_run=False,
        yes=True,   # auto-confirm in tests
    )


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def invoke(runner, aws_mock):
    """Invoke the CLI as a user would.

    Global flags (--output, --dry-run, --yes) are prepended automatically.
    moto intercepts all boto3 calls, so no real AWS credentials are needed.
    """
    def _invoke(
        *args: str,
        dry_run: bool = False,
        yes: bool = True,
        output: str = "json",
    ):
        root_args = ["--output", output, "--region", "us-east-1", "--no-cache"]
        if dry_run:
            root_args.append("--dry-run")
        if yes:
            root_args.append("--yes")
        return runner.invoke(cli, root_args + list(args), catch_exceptions=True)
    return _invoke
