"""Integration tests for the Lambda plugin using moto."""
from __future__ import annotations

import io
import json
import zipfile

import boto3
import pytest
from moto import mock_aws

from aws.main import cli
from tests.conftest import *  # noqa: F401, F403


@pytest.fixture
def iam_client():
    return boto3.client("iam", region_name="us-east-1")


@pytest.fixture
def lambda_client():
    return boto3.client("lambda", region_name="us-east-1")


@pytest.fixture
def lambda_role(aws_mock, iam_client):
    trust = json.dumps({
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Principal": {"Service": "lambda.amazonaws.com"},
            "Action": "sts:AssumeRole",
        }],
    })
    resp = iam_client.create_role(RoleName="LambdaRole", AssumeRolePolicyDocument=trust)
    return resp["Role"]["Arn"]


def _make_zip() -> bytes:
    """Create a minimal valid Lambda zip."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("index.py", "def handler(event, context): return {'statusCode': 200}")
    return buf.getvalue()


@pytest.fixture
def fn(aws_mock, lambda_client, lambda_role):
    lambda_client.create_function(
        FunctionName="my-fn",
        Runtime="python3.12",
        Role=lambda_role,
        Handler="index.handler",
        Code={"ZipFile": _make_zip()},
    )
    return "my-fn"


# ── list ──────────────────────────────────────────────────────────────────────
def test_functions_list(invoke, aws_mock, fn):
    result = invoke("lambda", "functions", "list")
    assert result.exit_code == 0
    names = [f["FunctionName"] for f in json.loads(result.output)]
    assert "my-fn" in names


def test_functions_list_empty(invoke, aws_mock):
    result = invoke("lambda", "functions", "list")
    assert result.exit_code == 0
    assert json.loads(result.output) == []


# ── describe ──────────────────────────────────────────────────────────────────
def test_functions_describe(invoke, aws_mock, fn):
    result = invoke("lambda", "functions", "describe", "my-fn")
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["FunctionName"] == "my-fn"
    assert data["Runtime"] == "python3.12"


def test_functions_describe_not_found(invoke, aws_mock):
    result = invoke("lambda", "functions", "describe", "ghost-fn")
    assert result.exit_code != 0


# ── invoke ────────────────────────────────────────────────────────────────────
@pytest.mark.skipif(
    not __import__("importlib.util", fromlist=["find_spec"]).find_spec("docker"),
    reason="Lambda invocation via moto requires the 'docker' package",
)
def test_functions_invoke(invoke, aws_mock, fn):
    result = invoke(
        "lambda", "functions", "invoke", "my-fn",
        "--payload", '{"key": "value"}',
    )
    assert result.exit_code == 0


# ── deploy ────────────────────────────────────────────────────────────────────
def test_functions_deploy(invoke, aws_mock, fn, tmp_path):
    zip_path = tmp_path / "code.zip"
    zip_path.write_bytes(_make_zip())
    result = invoke("lambda", "functions", "deploy", "my-fn", str(zip_path))
    assert result.exit_code == 0
    assert "Code updated" in result.output


# ── delete ────────────────────────────────────────────────────────────────────
def test_functions_delete(invoke, aws_mock, fn, lambda_client):
    result = invoke("lambda", "functions", "delete", "my-fn")
    assert result.exit_code == 0
    fns = [f["FunctionName"] for f in lambda_client.list_functions()["Functions"]]
    assert "my-fn" not in fns


# ── dry-run ───────────────────────────────────────────────────────────────────
def test_functions_delete_dry_run(invoke, aws_mock, fn, lambda_client):
    result = invoke("lambda", "functions", "delete", "my-fn", dry_run=True)
    assert result.exit_code == 0
    assert "DRY RUN" in result.output
    fns = [f["FunctionName"] for f in lambda_client.list_functions()["Functions"]]
    assert "my-fn" in fns
