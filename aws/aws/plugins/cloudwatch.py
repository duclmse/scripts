"""Amazon CloudWatch plugin — metrics, alarms, and Logs."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone, timedelta
from typing import Any

from ..context import AppContext
from core.decorators import arg, choice, mutating, Command
from core.logger import Logger

cw_grp = Command.group("cloudwatch", help="Amazon CloudWatch operations.")


# ╔══════════════════════════════════════════════════════════════════════════════
# ║  metrics
# ╚══════════════════════════════════════════════════════════════════════════════
metrics = cw_grp.group("metrics", help="CloudWatch metric operations.")


@metrics.register("list", help="List CloudWatch metrics.", args=[
    arg("--namespace", "-n", help="Filter by namespace (e.g. AWS/EC2)."),
    arg("--region", "-r", help="Override AWS region."),
])
def metrics_list(app: AppContext, args: argparse.Namespace) -> None:
    cw = app.client("cloudwatch", region=args.region)
    kwargs: dict[str, Any] = {}
    if args.namespace:
        kwargs["Namespace"] = args.namespace
    cache_key = f"cw:metrics:{args.region or app.region}:{args.namespace}"

    def _fetch() -> list[dict]:
        paginator = cw.get_paginator("list_metrics")
        return [
            {
                "Namespace": m["Namespace"],
                "MetricName": m["MetricName"],
                "Dimensions": str({d["Name"]: d["Value"] for d in m.get("Dimensions", [])}),
            }
            for page in paginator.paginate(**kwargs)
            for m in page["Metrics"]
        ]

    app.out(app.cached(cache_key, _fetch, ttl=180))


@metrics.register("get", help="Retrieve metric statistics.", args=[
    arg("namespace"),
    arg("metric_name"),
    arg("--dimensions", "-d", action="append", metavar="Name=Value",
        help="Metric dimensions (repeatable)."),
    arg("--period", type=int, default=300, help="Period in seconds."),
    choice("--stat", ["Average", "Sum", "Minimum", "Maximum", "SampleCount"],
           default="Average"),
    arg("--hours", type=int, default=1, help="Look-back window in hours."),
    arg("--region", "-r", help="Override AWS region."),
])
def metrics_get(app: AppContext, args: argparse.Namespace) -> None:
    cw = app.client("cloudwatch", region=args.region)
    end = datetime.now(timezone.utc)
    start = end - timedelta(hours=args.hours)
    dimensions = tuple(args.dimensions or [])
    dims = [{"Name": k, "Value": v} for item in dimensions for k, v in [item.split("=", 1)]]
    resp = cw.get_metric_statistics(
        Namespace=args.namespace,
        MetricName=args.metric_name,
        Dimensions=dims,
        StartTime=start,
        EndTime=end,
        Period=args.period,
        Statistics=[args.stat],
    )
    datapoints = sorted(resp["Datapoints"], key=lambda dp: dp["Timestamp"])
    app.out([
        {"Timestamp": str(dp["Timestamp"]), args.stat: dp[args.stat], "Unit": dp.get("Unit", "")}
        for dp in datapoints
    ])


@metrics.register("put", help="Publish a custom metric data point.", args=[
    arg("namespace"),
    arg("metric_name"),
    arg("value", type=float),
    arg("--unit", default="None", help="Metric unit."),
    arg("--dimensions", "-d", action="append", metavar="Name=Value"),
    arg("--region", "-r", help="Override AWS region."),
])
@mutating()
def metrics_put(app: AppContext, args: argparse.Namespace) -> None:
    cw = app.client("cloudwatch", region=args.region)
    dimensions = tuple(args.dimensions or [])
    dims = [{"Name": k, "Value": v} for item in dimensions for k, v in [item.split("=", 1)]]
    cw.put_metric_data(
        Namespace=args.namespace,
        MetricData=[
            {
                "MetricName": args.metric_name,
                "Dimensions": dims,
                "Value": args.value,
                "Unit": args.unit,
                "Timestamp": datetime.now(timezone.utc),
            }
        ],
    )
    Logger.success(f"Published {args.namespace}/{args.metric_name}={args.value} ({args.unit}).")


# ╔══════════════════════════════════════════════════════════════════════════════
# ║  alarms
# ╚══════════════════════════════════════════════════════════════════════════════
alarms = cw_grp.group("alarms", help="CloudWatch alarm operations.")


@alarms.register("list", help="List CloudWatch alarms.", args=[
    arg("--state", default="", help="Filter by state (OK, ALARM, INSUFFICIENT_DATA)."),
    arg("--prefix", default="", help="Alarm name prefix."),
    arg("--region", "-r", help="Override AWS region."),
])
def alarms_list(app: AppContext, args: argparse.Namespace) -> None:
    cw = app.client("cloudwatch", region=args.region)
    kwargs: dict[str, Any] = {}
    if args.state:
        kwargs["StateValue"] = args.state
    if args.prefix:
        kwargs["AlarmNamePrefix"] = args.prefix

    def _fetch() -> list[dict]:
        paginator = cw.get_paginator("describe_alarms")
        return [
            {
                "AlarmName": a["AlarmName"],
                "State": a["StateValue"],
                "Metric": f"{a.get('Namespace', '')}/{a.get('MetricName', '')}",
                "Threshold": f"{a.get('ComparisonOperator', '')} {a.get('Threshold', '')}",
                "UpdatedTime": str(a.get("StateUpdatedTimestamp", "")),
            }
            for page in paginator.paginate(**kwargs)
            for a in page["MetricAlarms"]
        ]

    cache_key = f"cw:alarms:{args.region or app.region}:{args.state}:{args.prefix}"
    app.out(app.cached(cache_key, _fetch, ttl=60))


@alarms.register("delete", help="Delete one or more CloudWatch alarms.", args=[
    arg("alarm_names", nargs="+"),
    arg("--region", "-r", help="Override AWS region."),
])
@mutating(destructive=True)
def alarms_delete(app: AppContext, args: argparse.Namespace) -> None:
    cw = app.client("cloudwatch", region=args.region)
    cw.delete_alarms(AlarmNames=list(args.alarm_names))
    print(f"Deleted {len(args.alarm_names)} alarm(s).")


@alarms.register("set-state", help="Override the state of an alarm (useful for testing).", args=[
    arg("alarm_name"),
    arg("state", choices=["OK", "ALARM", "INSUFFICIENT_DATA"]),
    arg("--reason", default="Manually set via aws", help="Reason for state change."),
    arg("--region", "-r", help="Override AWS region."),
])
@mutating()
def alarms_set_state(app: AppContext, args: argparse.Namespace) -> None:
    cw = app.client("cloudwatch", region=args.region)
    cw.set_alarm_state(
        AlarmName=args.alarm_name,
        StateValue=args.state,
        StateReason=args.reason,
    )
    print(f"Alarm {args.alarm_name!r} set to {args.state}.")


# ╔══════════════════════════════════════════════════════════════════════════════
# ║  logs
# ╚══════════════════════════════════════════════════════════════════════════════
logs = cw_grp.group("logs", help="CloudWatch Logs operations.")


@logs.register("groups", help="List CloudWatch log groups.", args=[
    arg("--prefix", default="", help="Log group name prefix."),
    arg("--region", "-r", help="Override AWS region."),
])
def logs_groups(app: AppContext, args: argparse.Namespace) -> None:
    cwl = app.client("logs", region=args.region)
    kwargs: dict[str, Any] = {}
    if args.prefix:
        kwargs["logGroupNamePrefix"] = args.prefix

    def _fetch() -> list[dict]:
        paginator = cwl.get_paginator("describe_log_groups")
        return [
            {
                "LogGroupName": g["logGroupName"],
                "RetentionDays": g.get("retentionInDays", "Never"),
                "StoredBytes": g.get("storedBytes", 0),
            }
            for page in paginator.paginate(**kwargs)
            for g in page["logGroups"]
        ]

    cache_key = f"cw:log_groups:{args.region or app.region}:{args.prefix}"
    app.out(app.cached(cache_key, _fetch, ttl=120))


@logs.register("streams", help="List log streams in a log group.", args=[
    arg("log_group"),
    arg("--prefix", default="", help="Log stream name prefix."),
    arg("--region", "-r", help="Override AWS region."),
])
def logs_streams(app: AppContext, args: argparse.Namespace) -> None:
    cwl = app.client("logs", region=args.region)
    kwargs: dict[str, Any] = {
        "logGroupName": args.log_group,
        "orderBy": "LastEventTime",
        "descending": True,
    }
    if args.prefix:
        kwargs["logStreamNamePrefix"] = args.prefix
    paginator = cwl.get_paginator("describe_log_streams")
    rows = [
        {
            "StreamName": s["logStreamName"],
            "LastEvent": str(datetime.fromtimestamp(s.get("lastEventTimestamp", 0) / 1000, tz=timezone.utc)),
            "StoredBytes": s.get("storedBytes", 0),
        }
        for page in paginator.paginate(**kwargs)
        for s in page["logStreams"]
    ]
    app.out(rows)


@logs.register("events", help="Fetch log events from a specific stream.", args=[
    arg("log_group"),
    arg("log_stream"),
    arg("--limit", type=int, default=100, help="Maximum number of events to return."),
    arg("--region", "-r", help="Override AWS region."),
])
def logs_events(app: AppContext, args: argparse.Namespace) -> None:
    cwl = app.client("logs", region=args.region)
    resp = cwl.get_log_events(
        logGroupName=args.log_group,
        logStreamName=args.log_stream,
        limit=args.limit,
        startFromHead=False,
    )
    rows = [
        {
            "Timestamp": str(datetime.fromtimestamp(e["timestamp"] / 1000, tz=timezone.utc)),
            "Message": e["message"].rstrip(),
        }
        for e in resp["events"]
    ]
    app.out(rows)
