"""Integration tests for the IAM plugin using moto."""
from __future__ import annotations

import json

import boto3
import pytest
from moto import mock_aws

from aws.main import cli
from tests.conftest import *  # noqa: F401, F403


@pytest.fixture
def iam_client():
    return boto3.client("iam", region_name="us-east-1")


# ── users ──────────────────────────────────────────────────────────────────────

def test_users_list_empty(invoke, aws_mock):
    result = invoke("iam", "users", "list")
    assert result.exit_code == 0
    assert json.loads(result.output) == []


def test_users_create(invoke, aws_mock, iam_client):
    result = invoke("iam", "users", "create", "alice")
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["UserName"] == "alice"
    assert "Arn" in data


def test_users_list_after_create(invoke, aws_mock, iam_client):
    iam_client.create_user(UserName="bob")
    result = invoke("iam", "users", "list")
    assert result.exit_code == 0
    names = [u["UserName"] for u in json.loads(result.output)]
    assert "bob" in names


def test_users_delete(invoke, aws_mock, iam_client):
    iam_client.create_user(UserName="eve")
    result = invoke("iam", "users", "delete", "eve")
    assert result.exit_code == 0
    users = [u["UserName"] for u in iam_client.list_users()["Users"]]
    assert "eve" not in users


def test_users_describe(invoke, aws_mock, iam_client):
    iam_client.create_user(UserName="carol")
    result = invoke("iam", "users", "describe", "carol")
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["UserName"] == "carol"


# ── roles ──────────────────────────────────────────────────────────────────────

TRUST_POLICY = json.dumps({
    "Version": "2012-10-17",
    "Statement": [{
        "Effect": "Allow",
        "Principal": {"Service": "ec2.amazonaws.com"},
        "Action": "sts:AssumeRole",
    }],
})


def test_roles_list(invoke, aws_mock, iam_client):
    iam_client.create_role(RoleName="MyRole", AssumeRolePolicyDocument=TRUST_POLICY)
    result = invoke("iam", "roles", "list")
    assert result.exit_code == 0
    names = [r["RoleName"] for r in json.loads(result.output)]
    assert "MyRole" in names


def test_roles_create(invoke, aws_mock, tmp_path):
    trust_file = tmp_path / "trust.json"
    trust_file.write_text(TRUST_POLICY)
    result = invoke("iam", "roles", "create", "NewRole", "--trust-policy", str(trust_file))
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["RoleName"] == "NewRole"


def test_roles_delete(invoke, aws_mock, iam_client):
    iam_client.create_role(RoleName="ToDelete", AssumeRolePolicyDocument=TRUST_POLICY)
    result = invoke("iam", "roles", "delete", "ToDelete")
    assert result.exit_code == 0
    roles = [r["RoleName"] for r in iam_client.list_roles()["Roles"]]
    assert "ToDelete" not in roles


# ── policies ───────────────────────────────────────────────────────────────────

def test_policies_list_local(invoke, aws_mock):
    result = invoke("iam", "policies", "list", "--scope", "Local")
    assert result.exit_code == 0
    assert isinstance(json.loads(result.output), list)
