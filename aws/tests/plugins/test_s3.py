"""Integration tests for the S3 plugin using moto."""
from __future__ import annotations

import json
import os

import boto3
import pytest
from moto import mock_aws

from aws.main import cli
from tests.conftest import *  # noqa: F401, F403


@pytest.fixture
def s3_client():
    return boto3.client("s3", region_name="us-east-1")


@pytest.fixture
def bucket(s3_client, aws_mock):
    s3_client.create_bucket(Bucket="test-bucket")
    return "test-bucket"


# ── buckets list ───────────────────────────────────────────────────────────────

def test_buckets_list(invoke, aws_mock, bucket):
    result = invoke("s3", "buckets", "list")
    assert result.exit_code == 0
    data = json.loads(result.output)
    names = [b["Name"] for b in data]
    assert "test-bucket" in names


# ── buckets create / delete ────────────────────────────────────────────────────

def test_buckets_create(invoke, aws_mock, s3_client):
    result = invoke("s3", "buckets", "create", "new-bucket")
    assert result.exit_code == 0
    assert "new-bucket" in result.output


def test_buckets_delete(invoke, aws_mock, bucket, s3_client):
    result = invoke("s3", "buckets", "delete", bucket)
    assert result.exit_code == 0
    buckets = [b["Name"] for b in s3_client.list_buckets()["Buckets"]]
    assert bucket not in buckets


def test_buckets_delete_force(invoke, aws_mock, bucket, s3_client):
    # Put an object first.
    s3_client.put_object(Bucket=bucket, Key="file.txt", Body=b"data")
    result = invoke("s3", "buckets", "delete", bucket, "--force")
    assert result.exit_code == 0


# ── objects ls ─────────────────────────────────────────────────────────────────

def test_objects_ls_bucket(invoke, aws_mock, bucket, s3_client):
    s3_client.put_object(Bucket=bucket, Key="file.txt", Body=b"hello")
    result = invoke("s3", "objects", "ls", f"s3://{bucket}/")
    assert result.exit_code == 0
    data = json.loads(result.output)
    keys = [row["Key"] for row in data]
    assert "file.txt" in keys


def test_objects_ls_recursive(invoke, aws_mock, bucket, s3_client):
    s3_client.put_object(Bucket=bucket, Key="dir/a.txt", Body=b"a")
    s3_client.put_object(Bucket=bucket, Key="dir/b.txt", Body=b"b")
    result = invoke("s3", "objects", "ls", f"s3://{bucket}/dir/", "--recursive")
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert len(data) == 2


# ── objects put / get ──────────────────────────────────────────────────────────

def test_objects_put_and_get(invoke, aws_mock, bucket, tmp_path):
    src = tmp_path / "upload.txt"
    src.write_text("hello world")
    dest = tmp_path / "download.txt"

    result = invoke("s3", "objects", "put", str(src), f"s3://{bucket}/upload.txt")
    assert result.exit_code == 0

    result = invoke("s3", "objects", "get", f"s3://{bucket}/upload.txt", str(dest))
    assert result.exit_code == 0
    assert dest.read_text() == "hello world"


# ── objects rm ────────────────────────────────────────────────────────────────

def test_objects_rm(invoke, aws_mock, bucket, s3_client):
    s3_client.put_object(Bucket=bucket, Key="todelete.txt", Body=b"x")
    result = invoke("s3", "objects", "rm", f"s3://{bucket}/todelete.txt")
    assert result.exit_code == 0
    with pytest.raises(s3_client.exceptions.NoSuchKey):
        s3_client.get_object(Bucket=bucket, Key="todelete.txt")


def test_objects_rm_recursive(invoke, aws_mock, bucket, s3_client):
    for i in range(3):
        s3_client.put_object(Bucket=bucket, Key=f"logs/file{i}.log", Body=b"data")
    result = invoke("s3", "objects", "rm", f"s3://{bucket}/logs/", "--recursive")
    assert result.exit_code == 0


# ── presign ────────────────────────────────────────────────────────────────────

def test_objects_presign(invoke, aws_mock, bucket, s3_client):
    s3_client.put_object(Bucket=bucket, Key="asset.bin", Body=b"data")
    result = invoke("s3", "objects", "presign", f"s3://{bucket}/asset.bin", "--expires", "600")
    assert result.exit_code == 0
    url = result.output.strip()
    assert "asset.bin" in url
    assert url.startswith("https://")
