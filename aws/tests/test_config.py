"""Tests for aws.config."""
from __future__ import annotations

import os
import textwrap

import pytest

from aws.config import Config
from aws.exceptions import ConfigError


def test_defaults():
    cfg = Config()
    assert cfg.get("region") == "us-east-1"
    assert cfg.get("output") == "table"
    assert cfg.get("dry_run") is False


def test_load_yaml(tmp_path):
    yaml_content = textwrap.dedent("""\
        region: eu-west-1
        output: json
        log_level: DEBUG
        roles:
          dev: arn:aws:iam::123456789012:role/Dev
    """)
    p = tmp_path / "config.yaml"
    p.write_text(yaml_content)
    cfg = Config(str(p))
    assert cfg.get("region") == "eu-west-1"
    assert cfg.get("output") == "json"
    assert cfg.get("log_level") == "DEBUG"


def test_invalid_yaml_raises(tmp_path):
    p = tmp_path / "bad.yaml"
    p.write_text(": :\nnot valid yaml:")
    with pytest.raises(ConfigError):
        Config(str(p))


def test_env_override(monkeypatch, tmp_path):
    p = tmp_path / "config.yaml"
    p.write_text("region: us-east-1\n")
    monkeypatch.setenv("AWS_REGION", "ap-southeast-1")
    cfg = Config(str(p))
    assert cfg.get("region") == "ap-southeast-1"


def test_env_bool_true(monkeypatch):
    monkeypatch.setenv("AWS_DRY_RUN", "true")
    cfg = Config()
    assert cfg.get("dry_run") is True


def test_env_bool_false(monkeypatch):
    monkeypatch.setenv("AWS_DRY_RUN", "false")
    cfg = Config()
    assert cfg.get("dry_run") is False


def test_role_arn_passthrough():
    cfg = Config()
    arn = "arn:aws:iam::123456789012:role/MyRole"
    assert cfg.role_arn(arn) == arn


def test_role_arn_alias(tmp_path):
    yaml_content = "roles:\n  prod: arn:aws:iam::111222333444:role/ProdRole\n"
    p = tmp_path / "c.yaml"
    p.write_text(yaml_content)
    cfg = Config(str(p))
    assert cfg.role_arn("prod") == "arn:aws:iam::111222333444:role/ProdRole"
    assert cfg.role_arn("unknown") is None


def test_set_overrides():
    cfg = Config()
    cfg.set("region", "sa-east-1")
    assert cfg.get("region") == "sa-east-1"


def test_as_dict_includes_roles(tmp_path):
    p = tmp_path / "c.yaml"
    p.write_text("roles:\n  ro: arn:aws:iam::123:role/RO\n")
    cfg = Config(str(p))
    d = cfg.as_dict()
    assert "roles" in d
    assert d["roles"]["ro"] == "arn:aws:iam::123:role/RO"
