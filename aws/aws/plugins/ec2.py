"""Amazon EC2 plugin — instances, snapshots, AMIs, key pairs, security groups, VPCs."""
from __future__ import annotations

from typing import Any
from botocore.exceptions import ClientError

from ..context import AppContext
from ..core.decorators import Command, arg, mutating
from ..exceptions import ResourceNotFoundError
from core.logger import Logger

# ── Root group ────────────────────────────────────────────────────────────────
ec2_group = Command.group("ec2", help="Amazon EC2 operations.")


# ── Shared helpers ────────────────────────────────────────────────────────────

def _tag_filters(raw: tuple[str, ...]) -> list[dict]:
    filters = []
    for item in raw:
        if "=" not in item:
            raise ValueError(f"Tags must be Key=Value, got {item!r}")
        k, v = item.split("=", 1)
        filters.append({"Name": f"tag:{k}", "Values": [v]})
    return filters


def _fmt_instance(inst: dict) -> dict:
    tags = {t["Key"]: t["Value"] for t in inst.get("Tags", [])}
    return {
        "InstanceId": inst["InstanceId"],
        "Name": tags.get("Name", ""),
        "State": inst["State"]["Name"],
        "Type": inst["InstanceType"],
        "AZ": inst["Placement"]["AvailabilityZone"],
        "PublicIP": inst.get("PublicIpAddress", ""),
        "PrivateIP": inst.get("PrivateIpAddress", ""),
        "LaunchTime": str(inst.get("LaunchTime", "")),
    }


# ╔══════════════════════════════════════════════════════════════════════════════
# ║  instances
# ╚══════════════════════════════════════════════════════════════════════════════
instances = ec2_group.group("instances", help="EC2 instance operations.")


@instances.register("list", help="List EC2 instances.", args=[
    arg("--state", "-s", multiple=True, default=("running"), show_default=True,
        help="Filter by instance state (repeatable)."),
    arg("--tag", "-t", multiple=True, metavar="Key=Value",
        help="Filter by tag (repeatable)."),
    arg("--id", "ids", multiple=True, metavar="INSTANCE_ID",
        help="Limit to specific instance IDs."),
    arg("--region", "-r", help="Override AWS region.")
])
def instances_list(app: AppContext, state: tuple, tag: tuple, ids: tuple, region: str | None) -> None:
    """List EC2 instances."""
    ec2 = app.client("ec2", region=region)
    filters = [{"Name": "instance-state-name", "Values": list(state)}] + _tag_filters(tag)
    cache_key = f"ec2:instances:{region or app.region}:{state}:{tag}:{ids}"

    def _fetch() -> list[dict]:
        kwargs: dict[str, Any] = {"Filters": filters}
        if ids:
            kwargs["InstanceIds"] = list(ids)
        paginator = ec2.get_paginator("describe_instances")
        return [
            _fmt_instance(inst)
            for page in paginator.paginate(**kwargs)
            for res in page["Reservations"]
            for inst in res["Instances"]
        ]

    results = app.cached(cache_key, _fetch, ttl=60)
    app.out(results or [{"msg": "No instances found."}])


@instances.register("describe", help="Show full details of a single instance.", args=[
    arg("instance_id"),
    arg("--region", "-r", help="Override AWS region.")
])
def instances_describe(app: AppContext, instance_id: str, region: str | None) -> None:
    """Show full details of a single instance."""
    ec2 = app.client("ec2", region=region)
    try:
        resp = ec2.describe_instances(InstanceIds=[instance_id])
    except ClientError as exc:
        if "InvalidInstanceID" in str(exc):
            raise ResourceNotFoundError(f"Instance {instance_id!r} not found.") from exc
        raise
    reservations = resp.get("Reservations", [])
    if not reservations:
        raise ResourceNotFoundError(f"Instance {instance_id!r} not found.")
    app.out(reservations[0]["Instances"][0])


@instances.register("start", help="Start stopped EC2 instances.", args=[
    arg("instance_ids", nargs=-1, required=True),
    arg("--region", "-r", help="Override AWS region.")
])
@mutating()
def instances_start(app: AppContext, instance_ids: tuple, region: str | None) -> None:
    """Start stopped EC2 instances."""
    ec2 = app.client("ec2", region=region)
    resp = ec2.start_instances(InstanceIds=list(instance_ids))
    app.out([
        {
            "InstanceId": s["InstanceId"],
            "Previous": s["PreviousState"]["Name"],
            "Current": s["CurrentState"]["Name"],
        }
        for s in resp["StartingInstances"]
    ])


@instances.register("stop", help="Stop running EC2 instances.", args=[
    arg("instance_ids", nargs=-1, required=True),
    arg("--force", is_flag=True, help="Force stop (may cause data loss)."),
    arg("--region", "-r", help="Override AWS region.")
])
@mutating()
def instances_stop(app: AppContext, instance_ids: tuple, force: bool, region: str | None) -> None:
    """Stop running EC2 instances."""
    ec2 = app.client("ec2", region=region)
    resp = ec2.stop_instances(InstanceIds=list(instance_ids), Force=force)
    app.out([
        {
            "InstanceId": s["InstanceId"],
            "Previous": s["PreviousState"]["Name"],
            "Current": s["CurrentState"]["Name"],
        }
        for s in resp["StoppingInstances"]
    ])


@instances.register("terminate", help="Permanently terminate EC2 instances.", args=[
    arg("instance_ids", nargs=-1, required=True),
    arg("--region", "-r", help="Override AWS region.")
])
@mutating(destructive=True)
def instances_terminate(app: AppContext, instance_ids: tuple, region: str | None) -> None:
    """Permanently terminate EC2 instances."""
    ec2 = app.client("ec2", region=region)
    resp = ec2.terminate_instances(InstanceIds=list(instance_ids))
    app.out([
        {
            "InstanceId": s["InstanceId"],
            "Previous": s["PreviousState"]["Name"],
            "Current": s["CurrentState"]["Name"],
        }
        for s in resp["TerminatingInstances"]
    ])


@instances.register("reboot", help="Reboot EC2 instances.", args=[
    arg("instance_ids", nargs=-1, required=True),
    arg("--region", "-r", help="Override AWS region.")
])
@mutating()
def instances_reboot(app: AppContext, instance_ids: tuple, region: str | None) -> None:
    """Reboot EC2 instances."""
    ec2 = app.client("ec2", region=region)
    ec2.reboot_instances(InstanceIds=list(instance_ids))
    Logger.warn(f"Reboot requested for: {', '.join(instance_ids)}")


# ╔══════════════════════════════════════════════════════════════════════════════
# ║  snapshots
# ╚══════════════════════════════════════════════════════════════════════════════
snapshots = ec2_group.group("snapshots", help="EBS snapshot operations.")


@snapshots.register("list", help="List EBS snapshots.", args=[
    arg("--owner", default="self", show_default=True,
        help="Snapshot owner (self, amazon, or account ID)."),
    arg("--tag", "-t", multiple=True, metavar="Key=Value", help="Filter by tag."),
    arg("--region", "-r", help="Override AWS region."),
])
def snapshots_list(app: AppContext, owner: str, tag: tuple, region: str | None) -> None:
    """List EBS snapshots."""
    ec2 = app.client("ec2", region=region)
    filters = _tag_filters(tag)
    cache_key = f"ec2:snapshots:{region or app.region}:{owner}:{tag}"

    def _fetch() -> list[dict]:
        paginator = ec2.get_paginator("describe_snapshots")
        return [
            {
                "SnapshotId": s["SnapshotId"],
                "VolumeId": s["VolumeId"],
                "State": s["State"],
                "Size(GiB)": s["VolumeSize"],
                "StartTime": str(s["StartTime"]),
                "Description": s.get("Description", ""),
            }
            for page in paginator.paginate(OwnerIds=[owner], Filters=filters)
            for s in page["Snapshots"]
        ]

    app.out(app.cached(cache_key, _fetch, ttl=120))


@snapshots.register("create", help="Create an EBS snapshot.", args=[
    arg("volume_id"),
    arg("--description", "-d", default="", help="Snapshot description."),
    arg("--tag", "-t", multiple=True, metavar="Key=Value", help="Tags to apply."),
    arg("--region", "-r", help="Override AWS region.")
])
@mutating()
def snapshots_create(app: AppContext, volume_id: str, description: str, tag: tuple, region: str | None) -> None:
    """Create an EBS snapshot from a volume."""
    ec2 = app.client("ec2", region=region)
    kwargs: dict[str, Any] = {"VolumeId": volume_id, "Description": description}
    if tag:
        tags = [{"Key": k, "Value": v} for item in tag for k, v in [item.split("=", 1)]]
        kwargs["TagSpecifications"] = [{"ResourceType": "snapshot", "Tags": tags}]
    resp = ec2.create_snapshot(**kwargs)
    app.out({
        "SnapshotId": resp["SnapshotId"],
        "VolumeId": resp["VolumeId"],
        "State": resp["State"],
        "StartTime": str(resp["StartTime"]),
    })


@snapshots.register("delete", help="Delete an EBS snapshot.", args=[
    arg("snapshot_id"),
    arg("--region", "-r", help="Override AWS region.")
])
@mutating(destructive=True)
def snapshots_delete(app: AppContext, snapshot_id: str, region: str | None) -> None:
    """Delete an EBS snapshot."""
    ec2 = app.client("ec2", region=region)
    ec2.delete_snapshot(SnapshotId=snapshot_id)
    Logger.info(f"Snapshot {snapshot_id} deleted.")


# ╔══════════════════════════════════════════════════════════════════════════════
# ║  images (AMIs)
# ╚══════════════════════════════════════════════════════════════════════════════
images = ec2_group.group("images", help="Amazon Machine Image (AMI) operations.")


@images.register("list", help="List AMIs.", args=[
    arg("--owner", default="self", show_default=True),
    arg("--name", "name_filter", help="AMI name filter (wildcards supported)."),
    arg("--region", "-r", help="Override AWS region.")
])
def images_list(app: AppContext, owner: str, name_filter: str | None, region: str | None) -> None:
    """List AMIs."""
    ec2 = app.client("ec2", region=region)
    filters = []
    if name_filter:
        filters.append({"Name": "name", "Values": [name_filter]})
    resp = ec2.describe_images(Owners=[owner], Filters=filters)
    rows = [
        {
            "ImageId": img["ImageId"],
            "Name": img.get("Name", ""),
            "State": img["State"],
            "Arch": img.get("Architecture", ""),
            "CreationDate": img.get("CreationDate", ""),
        }
        for img in sorted(
            resp["Images"],
            key=lambda x: x.get("CreationDate", ""),
            reverse=True,
        )
    ]
    app.out(rows)


@images.register("deregister", help="Deregister an AMI.", args=[
    arg("image_id"),
    arg("--region", "-r", help="Override AWS region.")
])
@mutating(destructive=True)
def images_deregister(app: AppContext, image_id: str, region: str | None) -> None:
    """Deregister an AMI."""
    ec2 = app.client("ec2", region=region)
    ec2.deregister_image(ImageId=image_id)
    Logger.info(f"AMI {image_id} deregistered.")


# ╔══════════════════════════════════════════════════════════════════════════════
# ║  keypairs
# ╚══════════════════════════════════════════════════════════════════════════════
keypairs = ec2_group.group("keypairs", help="EC2 key pair operations.")


@keypairs.register("list", help="List key pairs.", args=[
    arg("--region", "-r", help="Override AWS region.")
])
def keypairs_list(app: AppContext, region: str | None) -> None:
    """List key pairs."""
    ec2 = app.client("ec2", region=region)
    resp = ec2.describe_key_pairs()
    app.out([
        {
            "KeyName": kp["KeyName"],
            "KeyPairId": kp.get("KeyPairId", ""),
            "Fingerprint": kp.get("KeyFingerprint", ""),
        }
        for kp in resp["KeyPairs"]
    ])


@keypairs.register("delete", help="Delete a key pair.", args=[
    arg("key_name"),
    arg("--region", "-r", help="Override AWS region.")
])
@mutating(destructive=True)
def keypairs_delete(app: AppContext, key_name: str, region: str | None) -> None:
    """Delete a key pair."""
    ec2 = app.client("ec2", region=region)
    ec2.delete_key_pair(KeyName=key_name)
    Logger.info(f"Key pair {key_name!r} deleted.")


# ╔══════════════════════════════════════════════════════════════════════════════
# ║  security groups
# ╚══════════════════════════════════════════════════════════════════════════════
sgs = ec2_group.group("sgs", help="Security group operations.")


@sgs.register("list", help="List security groups.", args=[
    arg("--vpc", help="Filter by VPC ID."),
    arg("--region", "-r", help="Override AWS region.")
])
def sgs_list(app: AppContext, vpc: str | None, region: str | None) -> None:
    """List security groups."""
    ec2 = app.client("ec2", region=region)
    filters = [{"Name": "vpc-id", "Values": [vpc]}] if vpc else []
    resp = ec2.describe_security_groups(Filters=filters)
    app.out([
        {
            "GroupId": sg["GroupId"],
            "GroupName": sg["GroupName"],
            "VpcId": sg.get("VpcId", ""),
            "Description": sg.get("Description", ""),
        }
        for sg in resp["SecurityGroups"]
    ])


# ╔══════════════════════════════════════════════════════════════════════════════
# ║  VPCs
# ╚══════════════════════════════════════════════════════════════════════════════
vpcs = ec2_group.group("vpcs", help="VPC operations.")


@vpcs.register("list", help="List VPCs.", args=[
    arg("--region", "-r", help="Override AWS region.")
])
def vpcs_list(app: AppContext, region: str | None) -> None:
    """List VPCs."""
    ec2 = app.client("ec2", region=region)
    resp = ec2.describe_vpcs()
    app.out([
        {
            "VpcId": v["VpcId"],
            "CidrBlock": v["CidrBlock"],
            "IsDefault": v["IsDefault"],
            "State": v["State"],
            "Name": next(
                (t["Value"] for t in v.get("Tags", []) if t["Key"] == "Name"),
                "",
            ),
        } for v in resp["Vpcs"]
    ])
