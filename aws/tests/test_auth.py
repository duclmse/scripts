"""Tests for aws.auth — credential caching and role assumption."""
from __future__ import annotations

import time

import boto3
import pytest
from moto import mock_aws

from aws.auth import Auth, _REFRESH_BUFFER_S
from aws.cache import Cache
from aws.config import Config
from aws.exceptions import AuthError


@pytest.fixture
def auth_setup(tmp_path):
    cfg = Config()
    cache = Cache(cache_dir=str(tmp_path))
    auth = Auth(cfg, cache)
    return auth, cache


@mock_aws
def test_whoami_returns_identity(auth_setup):
    auth, _ = auth_setup
    identity = auth.whoami()
    assert "Account" in identity
    assert "Arn" in identity
    assert "UserId" in identity


@mock_aws
def test_session_reuse(auth_setup):
    """The same session should be returned on repeated calls (pool hit)."""
    auth, _ = auth_setup
    s1 = auth.session(region="us-east-1")
    s2 = auth.session(region="us-east-1")
    assert s1 is s2


@mock_aws
def test_different_regions_create_different_sessions(auth_setup):
    auth, _ = auth_setup
    s1 = auth.session(region="us-east-1")
    s2 = auth.session(region="eu-west-1")
    assert s1 is not s2


@mock_aws
def test_assume_role_caches_credentials(auth_setup, tmp_path):
    auth, cache = auth_setup

    # Create a role that moto will let us assume.
    iam = boto3.client("iam", region_name="us-east-1")
    import json
    trust = json.dumps({
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Principal": {"Service": "ec2.amazonaws.com"},
            "Action": "sts:AssumeRole",
        }],
    })
    role = iam.create_role(RoleName="TestRole", AssumeRolePolicyDocument=trust)
    role_arn = role["Role"]["Arn"]

    # First assume — should call STS and populate cache.
    sess = auth._assume_role(boto3.Session(region_name="us-east-1"), role_arn, "us-east-1")
    assert sess is not None
    cached = cache.get(f"role_creds:{role_arn}")
    assert cached is not None
    assert "creds" in cached

    # Second assume — should use the cache (no new STS call).
    sess2 = auth._assume_role(boto3.Session(region_name="us-east-1"), role_arn, "us-east-1")
    assert sess2 is not None


@mock_aws
def test_assume_role_refreshes_near_expiry(auth_setup, tmp_path):
    auth, cache = auth_setup

    iam = boto3.client("iam", region_name="us-east-1")
    import json
    trust = json.dumps({
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Principal": {"Service": "ec2.amazonaws.com"},
            "Action": "sts:AssumeRole",
        }],
    })
    role = iam.create_role(RoleName="RefreshRole", AssumeRolePolicyDocument=trust)
    role_arn = role["Role"]["Arn"]

    # Seed cache with credentials that are about to expire (within buffer window).
    soon = time.time() + _REFRESH_BUFFER_S - 10
    cache.set(
        f"role_creds:{role_arn}",
        {"creds": {"AccessKeyId": "OLD", "SecretAccessKey": "OLD", "SessionToken": "OLD"}, "wall_exp": soon},
        ttl=600,
    )
    # Should detect near-expiry and re-assume.
    sess = auth._assume_role(boto3.Session(region_name="us-east-1"), role_arn, "us-east-1")
    refreshed = cache.get(f"role_creds:{role_arn}")
    assert refreshed["creds"]["AccessKeyId"] != "OLD"


@mock_aws
def test_unknown_role_alias_raises(auth_setup):
    auth, _ = auth_setup
    with pytest.raises(AuthError, match="Unknown role alias"):
        auth.session(role="nonexistent-alias")
