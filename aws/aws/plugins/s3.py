"""Amazon S3 plugin — buckets, objects, presigned URLs."""
from __future__ import annotations

import os
from typing import Any

from botocore.exceptions import ClientError

from ..context import AppContext
from ..core.decorators import Command, arg, choice, mutating
from ..exceptions import ResourceNotFoundError
from core.logger import Logger

s3 = Command.group("s3", help="Amazon S3 operations.")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_s3_uri(uri: str) -> tuple[str, str]:
    """Split ``s3://bucket/key`` → ``(bucket, key)``."""
    if not uri.startswith("s3://"):
        raise ValueError(f"Expected s3://bucket/key, got {uri!r}")
    path = uri[5:]
    parts = path.split("/", 1)
    bucket = parts[0]
    key = parts[1] if len(parts) > 1 else ""
    return bucket, key


def _human_size(n: int) -> str:
    size = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} PB"


# ╔══════════════════════════════════════════════════════════════════════════════
# ║  buckets
# ╚══════════════════════════════════════════════════════════════════════════════
buckets = s3.group("buckets", help="S3 bucket operations.")


@buckets.register("list", help="List all S3 buckets.")
def buckets_list(app: AppContext) -> None:
    """List all S3 buckets."""
    s3 = app.client("s3")

    def _fetch() -> list[dict]:
        resp = s3.list_buckets()
        return [
            {
                "Name": b["Name"],
                "CreationDate": str(b["CreationDate"]),
            }
            for b in resp.get("Buckets", [])
        ]

    app.out(app.cached("s3:buckets", _fetch, ttl=120))


@buckets.register("create", help="Create an S3 bucket.", args=[
    arg("bucket_name"),
    arg("--region", "-r", default=None, help="Bucket region (default: CLI region)."),
    arg("--private", is_flag=True, default=True, show_default=True,
        help="Block all public access (recommended).")
])
@mutating()
def buckets_create(app: AppContext, bucket_name: str, region: str | None, private: bool) -> None:
    """Create an S3 bucket."""
    effective_region = region or app.region or "us-east-1"
    s3 = app.client("s3", region=effective_region)
    kwargs: dict[str, Any] = {"Bucket": bucket_name}
    if effective_region != "us-east-1":
        kwargs["CreateBucketConfiguration"] = {"LocationConstraint": effective_region}
    s3.create_bucket(**kwargs)
    if private:
        s3.put_public_access_block(
            Bucket=bucket_name,
            PublicAccessBlockConfiguration={
                "BlockPublicAcls": True,
                "IgnorePublicAcls": True,
                "BlockPublicPolicy": True,
                "RestrictPublicBuckets": True,
            },
        )
    Logger.success(f"Bucket s3://{bucket_name} created in {effective_region}.")


@buckets.register("delete", help="Delete an S3 bucket.", args=[
    arg("bucket_name"),
    arg("--force", is_flag=True, help="Delete all objects before deleting the bucket.")
])
@mutating(destructive=True)
def buckets_delete(app: AppContext, bucket_name: str, force: bool) -> None:
    """Delete an S3 bucket."""
    s3 = app.client("s3")
    if force:
        # Empty the bucket first (handles versioning-aware deletion).
        paginator = s3.get_paginator("list_object_versions")
        for page in paginator.paginate(Bucket=bucket_name):
            objects = [
                {"Key": v["Key"], "VersionId": v["VersionId"]}
                for v in page.get("Versions", [])
            ] + [
                {"Key": m["Key"], "VersionId": m["VersionId"]}
                for m in page.get("DeleteMarkers", [])
            ]
            if objects:
                s3.delete_objects(Bucket=bucket_name, Delete={"Objects": objects})
    s3.delete_bucket(Bucket=bucket_name)
    Logger.success(f"Bucket s3://{bucket_name} deleted.")


@buckets.register("info", help="Show configuration details for a bucket.", args=[
    arg("bucket_name")
])
def buckets_info(app: AppContext, bucket_name: str) -> None:
    """Show configuration details for a bucket."""
    s3 = app.client("s3")
    info: dict[str, Any] = {"Bucket": bucket_name}
    try:
        loc = s3.get_bucket_location(Bucket=bucket_name)
        info["Region"] = loc.get("LocationConstraint") or "us-east-1"
    except ClientError:
        info["Region"] = "unknown"
    try:
        versioning = s3.get_bucket_versioning(Bucket=bucket_name)
        info["Versioning"] = versioning.get("Status", "Disabled")
    except ClientError:
        info["Versioning"] = "unknown"
    try:
        enc = s3.get_bucket_encryption(Bucket=bucket_name)
        rules = enc["ServerSideEncryptionConfiguration"]["Rules"]
        info["Encryption"] = rules[0]["ApplyServerSideEncryptionByDefault"]["SSEAlgorithm"]
    except ClientError:
        info["Encryption"] = "None"
    app.out(info)


# ╔══════════════════════════════════════════════════════════════════════════════
# ║  objects
# ╚══════════════════════════════════════════════════════════════════════════════
objects = s3.group("objects", help="S3 object operations.")


@objects.register("ls", help="List objects in a bucket or at a prefix.", args=[
    arg("uri", default="s3://"),
    arg("--recursive", "-r", is_flag=True, help="List all objects recursively."),
    arg("--max-keys", default=1000, show_default=True)
])
def objects_ls(app: AppContext, uri: str, recursive: bool, max_keys: int) -> None:
    """List objects in a bucket or at a prefix.

    URI may be ``s3://bucket`` or ``s3://bucket/prefix``.
    """
    if uri in ("s3://", ""):
        # No bucket specified — fall back to listing buckets.
        s3 = app.client("s3")
        resp = s3.list_buckets()
        app.out([{"Name": b["Name"], "CreationDate": str(b["CreationDate"])} for b in resp.get("Buckets", [])])
        return

    bucket, prefix = _parse_s3_uri(uri)
    s3 = app.client("s3")

    if recursive:
        paginator = s3.get_paginator("list_objects_v2")
        rows = [
            {
                "Key": obj["Key"],
                "Size": _human_size(obj["Size"]),
                "LastModified": str(obj["LastModified"]),
            }
            for page in paginator.paginate(Bucket=bucket, Prefix=prefix)
            for obj in page.get("Contents", [])
        ]
    else:
        resp = s3.list_objects_v2(Bucket=bucket, Prefix=prefix, Delimiter="/", MaxKeys=max_keys)
        rows = [
            {"Key": cp["Prefix"], "Size": "-", "LastModified": "-"}
            for cp in resp.get("CommonPrefixes", [])
        ] + [
            {
                "Key": obj["Key"],
                "Size": _human_size(obj["Size"]),
                "LastModified": str(obj["LastModified"]),
            }
            for obj in resp.get("Contents", [])
        ]
    app.out(rows)


@objects.register("put", help="Upload a local file to S3.", args=[
    arg("src"),
    arg("dest_uri"),
    arg("--content-type", help="Override Content-Type."),
    choice("--sse", ["AES256", "aws:kms", "none"], default="AES256",
           show_default=True, help="Server-side encryption algorithm.")
])
@mutating()
def objects_put(app: AppContext, src: str, dest_uri: str, content_type: str | None, sse: str) -> None:
    """Upload a local file to S3."""
    bucket, key = _parse_s3_uri(dest_uri)
    if not key:
        key = os.path.basename(src)
    s3 = app.client("s3")
    extra: dict[str, Any] = {}
    if content_type:
        extra["ContentType"] = content_type
    if sse != "none":
        extra["ServerSideEncryption"] = sse
    s3.upload_file(src, bucket, key, ExtraArgs=extra or None)
    Logger.success(f"Uploaded {src} → s3://{bucket}/{key}")


@objects.register("get", help="Download an S3 object to a local file.", args=[
    arg("src_uri"),
    arg("dest", required=False)
])
def objects_get(app: AppContext, src_uri: str, dest: str | None) -> None:
    """Download an S3 object to a local file."""
    bucket, key = _parse_s3_uri(src_uri)
    if not key:
        raise ValueError("URI must include an object key.")
    local = dest or os.path.basename(key)
    s3 = app.client("s3")
    s3.download_file(bucket, key, local)
    Logger.success(f"Downloaded s3://{bucket}/{key} → {local}")


@objects.register("rm", help="Delete an S3 object or all objects under a prefix.", args=[
    arg("uri"),
    arg("--recursive", "-r", help="Delete all objects under the prefix.")
])
@mutating(destructive=True)
def objects_rm(app: AppContext, uri: str, recursive: bool) -> None:
    """Delete an S3 object or all objects under a prefix."""
    bucket, key = _parse_s3_uri(uri)
    s3 = app.client("s3")
    if recursive:
        paginator = s3.get_paginator("list_objects_v2")
        deleted = 0
        for page in paginator.paginate(Bucket=bucket, Prefix=key):
            objects = [{"Key": obj["Key"]} for obj in page.get("Contents", [])]
            if objects:
                s3.delete_objects(Bucket=bucket, Delete={"Objects": objects})
                deleted += len(objects)
        Logger.success(f"Deleted {deleted} object(s) under s3://{bucket}/{key}")
    else:
        s3.delete_object(Bucket=bucket, Key=key)
        Logger.success(f"Deleted s3://{bucket}/{key}")


@objects.register("presign", help="Generate a presigned URL for an S3 object.", args=[
    arg("uri"),
    arg("--expires", default=3600, show_default=True, help="Expiry in seconds."),
    choice("--method", ["get_object", "put_object"], default="get_object",
           show_default=True, help="HTTP method for the presigned URL.")
])
def objects_presign(app: AppContext, uri: str, expires: int, method: str) -> None:
    """Generate a presigned URL for an S3 object."""
    bucket, key = _parse_s3_uri(uri)
    s3 = app.client("s3")
    url = s3.generate_presigned_url(
        ClientMethod=method,
        Params={"Bucket": bucket, "Key": key},
        ExpiresIn=expires,
    )
    Logger.success(url)


@objects.register("cp", help="Copy an object within S3.", args=[
    arg("src_uri"),
    arg("dest_uri")
])
@mutating()
def objects_cp(app: AppContext, src_uri: str, dest_uri: str) -> None:
    """Copy an object within S3."""
    src_bucket, src_key = _parse_s3_uri(src_uri)
    dest_bucket, dest_key = _parse_s3_uri(dest_uri)
    s3 = app.client("s3")
    s3.copy_object(
        CopySource={"Bucket": src_bucket, "Key": src_key},
        Bucket=dest_bucket,
        Key=dest_key,
    )
    Logger.success(f"Copied {src_uri} → {dest_uri}")
