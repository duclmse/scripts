"""AWS CodeCommit plugin — repositories and branches."""
from __future__ import annotations

import argparse
from typing import Any

from botocore.exceptions import ClientError

from ..context import AppContext
from ..core.decorators import arg, choice, flag, mutating, Command
from ..exceptions import ResourceNotFoundError

cc_grp = Command.group("codecommit", help="AWS CodeCommit operations.")


# ╔══════════════════════════════════════════════════════════════════════════════
# ║  repos
# ╚══════════════════════════════════════════════════════════════════════════════
repos = cc_grp.group("repos", help="CodeCommit repository operations.")


@repos.register("list", help="List CodeCommit repositories.", args=[
    arg("--region", "-r", help="Override AWS region."),
])
def repos_list(app: AppContext, args: argparse.Namespace) -> None:
    cc = app.client("codecommit", region=args.region)
    cache_key = f"codecommit:repos:{args.region or app.region}"

    def _fetch() -> list[dict]:
        paginator = cc.get_paginator("list_repositories")
        names = [r["repositoryName"] for page in paginator.paginate() for r in page["repositories"]]
        if not names:
            return []
        batch = cc.batch_get_repositories(repositoryNames=names)
        return [
            {
                "Name": r["repositoryName"],
                "Id": r["repositoryId"],
                "DefaultBranch": r.get("defaultBranch", ""),
                "LastModified": str(r.get("lastModifiedDate", "")),
                "Description": r.get("repositoryDescription", ""),
            }
            for r in batch["repositories"]
        ]

    app.out(app.cached(cache_key, _fetch, ttl=120))


@repos.register("describe", help="Show details for a CodeCommit repository.", args=[
    arg("repo_name"),
    arg("--region", "-r", help="Override AWS region."),
])
def repos_describe(app: AppContext, args: argparse.Namespace) -> None:
    cc = app.client("codecommit", region=args.region)
    try:
        resp = cc.get_repository(repositoryName=args.repo_name)
    except ClientError as exc:
        if "RepositoryDoesNotExistException" in str(exc):
            raise ResourceNotFoundError(f"Repository {args.repo_name!r} not found.") from exc
        raise
    r = resp["repositoryMetadata"]
    app.out({
        "Name": r["repositoryName"],
        "Id": r["repositoryId"],
        "Arn": r["Arn"],
        "DefaultBranch": r.get("defaultBranch", ""),
        "CloneUrlHttp": r.get("cloneUrlHttp", ""),
        "CloneUrlSsh": r.get("cloneUrlSsh", ""),
        "Description": r.get("repositoryDescription", ""),
        "LastModified": str(r.get("lastModifiedDate", "")),
    })


@repos.register("create", help="Create a CodeCommit repository.", args=[
    arg("repo_name"),
    arg("--description", "-d", default="", help="Repository description."),
    arg("--tag", "-t", action="append", metavar="Key=Value", help="Tags to apply (repeatable)."),
    arg("--region", "-r", help="Override AWS region."),
])
@mutating()
def repos_create(app: AppContext, args: argparse.Namespace) -> None:
    cc = app.client("codecommit", region=args.region)
    tag = tuple(args.tag or [])
    kwargs: dict[str, Any] = {"repositoryName": args.repo_name}
    if args.description:
        kwargs["repositoryDescription"] = args.description
    if tag:
        kwargs["tags"] = dict(item.split("=", 1) for item in tag)
    resp = cc.create_repository(**kwargs)
    r = resp["repositoryMetadata"]
    app.out({
        "Name": r["repositoryName"],
        "Id": r["repositoryId"],
        "Arn": r["Arn"],
        "CloneUrlHttp": r.get("cloneUrlHttp", ""),
    })


@repos.register("delete", help="Delete a CodeCommit repository.", args=[
    arg("repo_name"),
    arg("--region", "-r", help="Override AWS region."),
])
@mutating(destructive=True)
def repos_delete(app: AppContext, args: argparse.Namespace) -> None:
    cc = app.client("codecommit", region=args.region)
    cc.delete_repository(repositoryName=args.repo_name)
    print(f"Repository {args.repo_name!r} deleted.")


@repos.register("clone-url", help="Print the clone URL for a repository.", args=[
    arg("repo_name"),
    choice("--protocol", ["https", "ssh"], default="https"),
    arg("--region", "-r", help="Override AWS region."),
])
def repos_clone_url(app: AppContext, args: argparse.Namespace) -> None:
    cc = app.client("codecommit", region=args.region)
    try:
        resp = cc.get_repository(repositoryName=args.repo_name)
    except ClientError as exc:
        if "RepositoryDoesNotExistException" in str(exc):
            raise ResourceNotFoundError(f"Repository {args.repo_name!r} not found.") from exc
        raise
    meta = resp["repositoryMetadata"]
    url_key = "cloneUrlSsh" if args.protocol == "ssh" else "cloneUrlHttp"
    print(meta.get(url_key, "URL not available."))


# ╔══════════════════════════════════════════════════════════════════════════════
# ║  branches
# ╚══════════════════════════════════════════════════════════════════════════════
branches = cc_grp.group("branches", help="CodeCommit branch operations.")


@branches.register("list", help="List branches in a CodeCommit repository.", args=[
    arg("repo_name"),
    arg("--region", "-r", help="Override AWS region."),
])
def branches_list(app: AppContext, args: argparse.Namespace) -> None:
    cc = app.client("codecommit", region=args.region)
    paginator = cc.get_paginator("list_branches")
    names = [b for page in paginator.paginate(repositoryName=args.repo_name) for b in page["branches"]]
    app.out([{"BranchName": b} for b in sorted(names)])


@branches.register("create", help="Create a branch in a CodeCommit repository.", args=[
    arg("repo_name"),
    arg("branch_name"),
    arg("--commit-id", dest="commit_id", required=True, help="Commit ID to branch from."),
    arg("--region", "-r", help="Override AWS region."),
])
@mutating()
def branches_create(app: AppContext, args: argparse.Namespace) -> None:
    cc = app.client("codecommit", region=args.region)
    cc.create_branch(
        repositoryName=args.repo_name,
        branchName=args.branch_name,
        commitId=args.commit_id,
    )
    print(f"Branch {args.branch_name!r} created in {args.repo_name!r} at {args.commit_id}.")


@branches.register("delete", help="Delete a branch from a CodeCommit repository.", args=[
    arg("repo_name"),
    arg("branch_name"),
    arg("--region", "-r", help="Override AWS region."),
])
@mutating(destructive=True)
def branches_delete(app: AppContext, args: argparse.Namespace) -> None:
    cc = app.client("codecommit", region=args.region)
    cc.delete_branch(repositoryName=args.repo_name, branchName=args.branch_name)
    print(f"Branch {args.branch_name!r} deleted from {args.repo_name!r}.")
