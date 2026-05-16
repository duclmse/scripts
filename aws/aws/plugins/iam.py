"""AWS IAM plugin — users, roles, and policies."""
from __future__ import annotations

from typing import Any

from botocore.exceptions import ClientError

from ..context import AppContext
from ..core.decorators import Command, arg, choice, mutating
from ..exceptions import ResourceNotFoundError
from core.logger import Logger


iam = Command.group("iam", help="AWS IAM operations.")

# ╔══════════════════════════════════════════════════════════════════════════════
# ║  users
# ╚══════════════════════════════════════════════════════════════════════════════
users = iam.group("users", help="IAM user operations.")


@users.register("list", help="List IAM users.", args=[
    arg("--path", default="/", show_default=True, help="Path prefix filter.")
])
def users_list(app: AppContext, path: str) -> None:
    """List IAM users."""
    iam = app.client("iam")
    cache_key = f"iam:users:{path}"

    def _fetch() -> list[dict]:
        paginator = iam.get_paginator("list_users")
        return [
            {
                "UserName": u["UserName"],
                "UserId": u["UserId"],
                "Path": u["Path"],
                "CreateDate": str(u["CreateDate"]),
                "PasswordLastUsed": str(u.get("PasswordLastUsed", "never")),
            }
            for page in paginator.paginate(PathPrefix=path)
            for u in page["Users"]
        ]

    app.out(app.cached(cache_key, _fetch, ttl=120))


@users.register("create", help="Create an IAM user.", args=[
    arg("username"),
    arg("--path", default="/", show_default=True),
    arg("--tag", "-t", multiple=True, metavar="Key=Value", help="Tags to apply.")
])
@mutating()
def users_create(app: AppContext, username: str, path: str, tag: tuple) -> None:
    """Create an IAM user."""
    iam = app.client("iam")
    kwargs: dict[str, Any] = {"UserName": username, "Path": path}
    if tag:
        kwargs["Tags"] = [{"Key": k, "Value": v} for item in tag for k, v in [item.split("=", 1)]]
    resp = iam.create_user(**kwargs)
    u = resp["User"]
    app.out({"UserName": u["UserName"], "UserId": u["UserId"], "Arn": u["Arn"]})


@users.register("delete", help="Delete an IAM user.", args=[
    arg("username")
])
@mutating(destructive=True)
def users_delete(app: AppContext, username: str) -> None:
    """Delete an IAM user (detaches policies and removes from groups first)."""
    iam = app.client("iam")
    # Detach managed policies.
    for policy in iam.list_attached_user_policies(UserName=username)["AttachedPolicies"]:
        iam.detach_user_policy(UserName=username, PolicyArn=policy["PolicyArn"])
    # Delete inline policies.
    for pname in iam.list_user_policies(UserName=username)["PolicyNames"]:
        iam.delete_user_policy(UserName=username, PolicyName=pname)
    # Remove from groups.
    for g in iam.list_groups_for_user(UserName=username)["Groups"]:
        iam.remove_user_from_group(UserName=username, GroupName=g["GroupName"])
    # Delete access keys.
    for ak in iam.list_access_keys(UserName=username)["AccessKeyMetadata"]:
        iam.delete_access_key(UserName=username, AccessKeyId=ak["AccessKeyId"])
    iam.delete_user(UserName=username)
    Logger.success(f"User {username!r} deleted.")


@users.register("describe", help="Show detailed info for an IAM user.", args=[
    arg("username")
])
def users_describe(app: AppContext, username: str) -> None:
    """Show detailed info for an IAM user."""
    iam = app.client("iam")
    try:
        resp = iam.get_user(UserName=username)
    except ClientError as exc:
        if "NoSuchEntity" in str(exc):
            raise ResourceNotFoundError(f"User {username!r} not found.") from exc
        raise
    u = resp["User"]
    policies = iam.list_attached_user_policies(UserName=username)["AttachedPolicies"]
    app.out({
        "UserName": u["UserName"],
        "UserId": u["UserId"],
        "Arn": u["Arn"],
        "Path": u["Path"],
        "CreateDate": str(u["CreateDate"]),
        "AttachedPolicies": [p["PolicyName"] for p in policies],
    })


# ╔══════════════════════════════════════════════════════════════════════════════
# ║  roles
# ╚══════════════════════════════════════════════════════════════════════════════
roles = iam.group("roles", help="IAM role operations.")


@roles.register("list", help="List IAM roles.", args=[
    arg("--path", default="/", show_default=True)
])
def roles_list(app: AppContext, path: str) -> None:
    """List IAM roles."""
    iam = app.client("iam")

    def _fetch() -> list[dict]:
        paginator = iam.get_paginator("list_roles")
        return [
            {
                "RoleName": r["RoleName"],
                "RoleId": r["RoleId"],
                "Arn": r["Arn"],
                "CreateDate": str(r["CreateDate"]),
                "Description": r.get("Description", ""),
            }
            for page in paginator.paginate(PathPrefix=path)
            for r in page["Roles"]
        ]

    app.out(app.cached(f"iam:roles:{path}", _fetch, ttl=120))


@roles.register("create", help="Create an IAM role.", args=[
    arg("role_name"),
    arg("--trust-policy", required=True, help="Path to trust-policy JSON file."),
    arg("--description", default="", help="Role description.")
])
@mutating()
def roles_create(app: AppContext, role_name: str, trust_policy: str, description: str) -> None:
    """Create an IAM role."""
    import json
    with open(trust_policy) as fh:
        policy_doc = fh.read()
    iam = app.client("iam")
    resp = iam.create_role(
        RoleName=role_name,
        AssumeRolePolicyDocument=policy_doc,
        Description=description,
    )
    r = resp["Role"]
    app.out({"RoleName": r["RoleName"], "RoleId": r["RoleId"], "Arn": r["Arn"]})


@roles.register("delete", help="Delete an IAM role.", args=[
    arg("role_name")
])
@mutating(destructive=True)
def roles_delete(app: AppContext, role_name: str) -> None:
    """Delete an IAM role (detaches policies first)."""
    iam = app.client("iam")
    for policy in iam.list_attached_role_policies(RoleName=role_name)["AttachedPolicies"]:
        iam.detach_role_policy(RoleName=role_name, PolicyArn=policy["PolicyArn"])
    for pname in iam.list_role_policies(RoleName=role_name)["PolicyNames"]:
        iam.delete_role_policy(RoleName=role_name, PolicyName=pname)
    iam.delete_role(RoleName=role_name)
    Logger.success(f"Role {role_name!r} deleted.")


@roles.register("attach-policy", help="Attach a managed policy to a role.", args=[
    arg("role_name"),
    arg("policy_arn")
])
@mutating()
def roles_attach_policy(app: AppContext, role_name: str, policy_arn: str) -> None:
    """Attach a managed policy to a role."""
    iam = app.client("iam")
    iam.attach_role_policy(RoleName=role_name, PolicyArn=policy_arn)
    Logger.success(f"Policy {policy_arn} attached to role {role_name!r}.")


# ╔══════════════════════════════════════════════════════════════════════════════
# ║  policies
# ╚══════════════════════════════════════════════════════════════════════════════
policies = iam.group("policies", help="IAM policy operations.")


@policies.register("list", help="List IAM policies.", args=[
    choice("--scope", values=["All", "AWS", "Local"], default="Local",
           show_default=True, help="Policy scope.")
])
def policies_list(app: AppContext, scope: str) -> None:
    """List IAM policies."""
    iam = app.client("iam")

    def _fetch() -> list[dict]:
        paginator = iam.get_paginator("list_policies")
        return [
            {
                "PolicyName": p["PolicyName"],
                "PolicyId": p["PolicyId"],
                "Arn": p["Arn"],
                "AttachmentCount": p["AttachmentCount"],
                "CreateDate": str(p["CreateDate"]),
            }
            for page in paginator.paginate(Scope=scope)
            for p in page["Policies"]
        ]

    app.out(app.cached(f"iam:policies:{scope}", _fetch, ttl=120))


@policies.register("describe", help="Show a policy's default version document.", args=[
    arg("policy_arn")
])
def policies_describe(app: AppContext, policy_arn: str) -> None:
    """Show a policy's default version document."""
    import json
    from urllib.parse import unquote

    iam = app.client("iam")
    policy = iam.get_policy(PolicyArn=policy_arn)["Policy"]
    version_id = policy["DefaultVersionId"]
    doc = iam.get_policy_version(PolicyArn=policy_arn, VersionId=version_id)
    decoded = doc["PolicyVersion"]["Document"]
    app.out(decoded)
