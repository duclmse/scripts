"""Integration tests for the EC2 plugin using moto."""
from __future__ import annotations

import json

import boto3
import pytest
from moto import mock_aws

from aws.main import cli
from tests.conftest import *  # noqa: F401, F403  — re-import shared fixtures


@pytest.fixture
def ec2_client():
    return boto3.client("ec2", region_name="us-east-1")


@pytest.fixture
def running_instance(ec2_client):
    """Launch a single running t3.micro instance and return its ID."""
    resp = ec2_client.run_instances(
        ImageId="ami-12345678",
        MinCount=1,
        MaxCount=1,
        InstanceType="t3.micro",
        TagSpecifications=[{
            "ResourceType": "instance",
            "Tags": [{"Key": "Name", "Value": "test-instance"}],
        }],
    )
    return resp["Instances"][0]["InstanceId"]


# ── instances list ─────────────────────────────────────────────────────────────

def test_instances_list_running(invoke, aws_mock, ec2_client, running_instance):
    result = invoke("ec2", "instances", "list")
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    ids = [row["InstanceId"] for row in data]
    assert running_instance in ids


def test_instances_list_empty_when_no_instances(invoke, aws_mock):
    result = invoke("ec2", "instances", "list")
    assert result.exit_code == 0


def test_instances_list_filter_by_tag(invoke, aws_mock, ec2_client, running_instance):
    result = invoke("ec2", "instances", "list", "--tag", "Name=test-instance")
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert any(row["Name"] == "test-instance" for row in data)


# ── instances describe ─────────────────────────────────────────────────────────

def test_instances_describe(invoke, aws_mock, ec2_client, running_instance):
    result = invoke("ec2", "instances", "describe", running_instance)
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["InstanceId"] == running_instance


def test_instances_describe_not_found(invoke, aws_mock):
    result = invoke("ec2", "instances", "describe", "i-nonexistent")
    assert result.exit_code != 0


# ── instances stop / start ─────────────────────────────────────────────────────

def test_instances_stop_and_start(invoke, aws_mock, ec2_client, running_instance):
    result = invoke("ec2", "instances", "stop", running_instance)
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data[0]["Previous"] == "running"

    result = invoke("ec2", "instances", "start", running_instance)
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data[0]["Previous"] == "stopped"


# ── instances terminate ────────────────────────────────────────────────────────

def test_instances_terminate(invoke, aws_mock, ec2_client, running_instance):
    result = invoke("ec2", "instances", "terminate", running_instance)
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data[0]["InstanceId"] == running_instance


# ── dry-run ────────────────────────────────────────────────────────────────────

def test_instances_stop_dry_run(invoke, aws_mock, ec2_client, running_instance):
    result = invoke("ec2", "instances", "stop", running_instance, dry_run=True)
    assert result.exit_code == 0
    assert "DRY RUN" in result.output
    # Instance should still be running.
    resp = ec2_client.describe_instances(InstanceIds=[running_instance])
    state = resp["Reservations"][0]["Instances"][0]["State"]["Name"]
    assert state == "running"


# ── snapshots ──────────────────────────────────────────────────────────────────

def test_snapshots_list(invoke, aws_mock, ec2_client):
    # Create a volume, then a snapshot.
    vol = ec2_client.create_volume(AvailabilityZone="us-east-1a", Size=8)
    ec2_client.create_snapshot(VolumeId=vol["VolumeId"], Description="test snapshot")
    result = invoke("ec2", "snapshots", "list")
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert len(data) >= 1


def test_snapshots_create(invoke, aws_mock, ec2_client):
    vol = ec2_client.create_volume(AvailabilityZone="us-east-1a", Size=8)
    result = invoke(
        "ec2", "snapshots", "create", vol["VolumeId"],
        "--description", "my backup",
    )
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert "SnapshotId" in data


# ── VPCs ───────────────────────────────────────────────────────────────────────

def test_vpcs_list(invoke, aws_mock):
    result = invoke("ec2", "vpcs", "list")
    assert result.exit_code == 0
    # moto creates a default VPC in each region.
    data = json.loads(result.output)
    assert len(data) >= 1
