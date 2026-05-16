"""AWS Lambda plugin — list, invoke, deploy, and manage functions and layers."""
from __future__ import annotations

import argparse
import base64
import json
import os
import sys
from typing import Any

from botocore.exceptions import ClientError

from ..context import AppContext
from ..core.decorators import arg, choice, flag, mutating, Command
from ..exceptions import ResourceNotFoundError, ValidationError

lambda_grp = Command.group("lambda", help="AWS Lambda operations.")


# ╔══════════════════════════════════════════════════════════════════════════════
# ║  functions
# ╚══════════════════════════════════════════════════════════════════════════════
functions = lambda_grp.group("functions", help="Lambda function operations.")


@functions.register("list", help="List Lambda functions.", args=[
    arg("--region", "-r", help="Override AWS region.")]
)
def functions_list(app: AppContext, args: argparse.Namespace) -> None:
    lmb = app.client("lambda", region=args.region)
    cache_key = f"lambda:functions:{args.region or app.region}"

    def _fetch() -> list[dict]:
        paginator = lmb.get_paginator("list_functions")
        return [
            {
                "FunctionName": f["FunctionName"],
                "Runtime": f.get("Runtime", ""),
                "Handler": f.get("Handler", ""),
                "MemorySize": f.get("MemorySize", ""),
                "Timeout": f.get("Timeout", ""),
                "LastModified": f.get("LastModified", ""),
                "State": f.get("State", ""),
            }
            for page in paginator.paginate()
            for f in page["Functions"]
        ]

    app.out(app.cached(cache_key, _fetch, ttl=60))


@functions.register("describe", args=[
    arg("function_name"),
    arg("--region", "-r", help="Override AWS region."),
], help="Show configuration details for a Lambda function.")
def functions_describe(app: AppContext, args: argparse.Namespace) -> None:
    lmb = app.client("lambda", region=args.region)
    try:
        resp = lmb.get_function(FunctionName=args.function_name)
    except ClientError as exc:
        if "ResourceNotFoundException" in str(exc):
            raise ResourceNotFoundError(f"Function {args.function_name!r} not found.") from exc
        raise
    config = resp["Configuration"]
    app.out({
        "FunctionName": config["FunctionName"],
        "FunctionArn": config["FunctionArn"],
        "Runtime": config.get("Runtime", ""),
        "Handler": config.get("Handler", ""),
        "Role": config.get("Role", ""),
        "MemorySize": config.get("MemorySize", ""),
        "Timeout": config.get("Timeout", ""),
        "State": config.get("State", ""),
        "LastModified": config.get("LastModified", ""),
        "Description": config.get("Description", ""),
        "Environment": config.get("Environment", {}).get("Variables", {}),
    })


@functions.register("invoke", help="Invoke a Lambda function synchronously or asynchronously.", args=[
    arg("function_name"),
    arg("--payload", default="{}", help="JSON payload string or @file.json to read from a file."),
    choice("--invocation-type", ["RequestResponse", "Event", "DryRun"], default="RequestResponse"),
    choice("--log-type", ["None", "Tail"], default="None"),
    arg("--region", "-r", help="Override AWS region."),
])
def functions_invoke(app: AppContext, args: argparse.Namespace) -> None:
    lmb = app.client("lambda", region=args.region)

    payload = args.payload
    if payload.startswith("@"):
        with open(payload[1:]) as fh:
            payload_bytes = fh.read().encode()
    else:
        payload_bytes = payload.encode()

    resp = lmb.invoke(
        FunctionName=args.function_name,
        InvocationType=args.invocation_type,
        LogType=args.log_type,
        Payload=payload_bytes,
    )
    body = resp["Payload"].read().decode()

    if args.log_type == "Tail" and "LogResult" in resp:
        log_output = base64.b64decode(resp["LogResult"]).decode(errors="replace")
        print("=== Execution Log ===", file=sys.stderr)
        print(log_output, file=sys.stderr)

    if "FunctionError" in resp:
        print(f"Function error ({resp['FunctionError']}): {body}", file=sys.stderr)
    else:
        try:
            app.out(json.loads(body))
        except json.JSONDecodeError:
            print(body)


@functions.register("deploy", help="Deploy new code to an existing Lambda function.", args=[
    arg("function_name"),
    arg("zip_file"),
    arg("--handler", help="New handler (e.g. index.handler)."),
    arg("--env", "-e", action="append", metavar="KEY=VALUE",
        help="Environment variable overrides (repeatable)."),
    arg("--region", "-r", help="Override AWS region."),
])
@mutating()
def functions_deploy(app: AppContext, args: argparse.Namespace) -> None:
    if not os.path.isfile(args.zip_file):
        raise ValidationError(f"zip_file {args.zip_file!r} is not a valid file.")
    lmb = app.client("lambda", region=args.region)
    with open(args.zip_file, "rb") as fh:
        zip_bytes = fh.read()

    code_resp = lmb.update_function_code(
        FunctionName=args.function_name,
        ZipFile=zip_bytes,
        Publish=True,
    )
    print(f"Code updated. Version: {code_resp.get('Version', 'n/a')}")

    env = tuple(args.env or [])
    updates: dict[str, Any] = {}
    if args.handler:
        updates["Handler"] = args.handler
    if env:
        current = lmb.get_function_configuration(FunctionName=args.function_name)
        current_env = current.get("Environment", {}).get("Variables", {})
        for kv in env:
            k, _, v = kv.partition("=")
            current_env[k] = v
        updates["Environment"] = {"Variables": current_env}

    if updates:
        lmb.update_function_configuration(FunctionName=args.function_name, **updates)
        print("Configuration updated.")


@functions.register("delete", help="Delete a Lambda function.", args=[
    arg("function_name"),
    arg("--qualifier", help="Version or alias to delete (omit for whole function)."),
    arg("--region", "-r", help="Override AWS region."),
])
@mutating(destructive=True)
def functions_delete(app: AppContext, args: argparse.Namespace) -> None:
    lmb = app.client("lambda", region=args.region)
    kwargs: dict[str, Any] = {"FunctionName": args.function_name}
    if args.qualifier:
        kwargs["Qualifier"] = args.qualifier
    lmb.delete_function(**kwargs)
    print(f"Function {args.function_name!r} deleted.")


@functions.register("list-versions", help="List published versions of a Lambda function.", args=[
    arg("function_name"),
    arg("--region", "-r", help="Override AWS region."),
])
def functions_list_versions(app: AppContext, args: argparse.Namespace) -> None:
    lmb = app.client("lambda", region=args.region)
    paginator = lmb.get_paginator("list_versions_by_function")
    rows = [
        {"Version": v["Version"], "LastModified": v["LastModified"], "Description": v.get("Description", "")}
        for page in paginator.paginate(FunctionName=args.function_name)
        for v in page["Versions"]
    ]
    app.out(rows)


# ╔══════════════════════════════════════════════════════════════════════════════
# ║  layers
# ╚══════════════════════════════════════════════════════════════════════════════
layers = lambda_grp.group("layers", help="Lambda layer operations.")


@layers.register("list", help="List Lambda layers.", args=[
    arg("--compatible-runtime", dest="compatible_runtime",
        help="Filter by runtime (e.g. python3.12)."),
    arg("--region", "-r", help="Override AWS region."),
])
def layers_list(app: AppContext, args: argparse.Namespace) -> None:
    lmb = app.client("lambda", region=args.region)
    kwargs: dict[str, Any] = {}
    if args.compatible_runtime:
        kwargs["CompatibleRuntime"] = args.compatible_runtime
    paginator = lmb.get_paginator("list_layers")
    rows = [
        {
            "LayerName": layer["LayerName"],
            "LatestVersion": layer.get("LatestMatchingVersion", {}).get("Version", ""),
            "Description": layer.get("LatestMatchingVersion", {}).get("Description", ""),
        }
        for page in paginator.paginate(**kwargs)
        for layer in page["Layers"]
    ]
    app.out(rows)
