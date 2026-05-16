"""AWS Cost Explorer plugin — usage, forecasts, and anomaly detection."""
from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta
from typing import Any

from ..context import AppContext
from ..core.decorators import arg, choice, flag, Command
from ..exceptions import ValidationError

cost_grp = Command.group("cost", help="AWS Cost Explorer operations.")


@cost_grp.register("usage", help="Show cost and usage breakdown.", args=[
    arg("--start", default=date.today().replace(day=1).isoformat(),
        help="Start date (YYYY-MM-DD)."),
    arg("--end", default=date.today().isoformat(),
        help="End date (YYYY-MM-DD, exclusive)."),
    choice("--granularity", ["DAILY", "MONTHLY", "HOURLY"], default="MONTHLY"),
    choice("--group-by", ["SERVICE", "REGION", "LINKED_ACCOUNT", "USAGE_TYPE", "TAG"],
           default="SERVICE"),
    arg("--tag-key", dest="tag_key", default="", help="Tag key when --group-by TAG."),
    choice("--metric", ["BlendedCost", "UnblendedCost", "AmortizedCost", "UsageQuantity"],
           default="UnblendedCost"),
])
def usage(app: AppContext, args: argparse.Namespace) -> None:
    ce = app.client("ce", region="us-east-1")  # Cost Explorer is global (only us-east-1 endpoint)
    if args.group_by == "TAG" and not args.tag_key:
        raise ValidationError("--tag-key is required when --group-by TAG.")
    group_def: dict[str, Any] = {"Type": args.group_by if args.group_by != "TAG" else "TAG"}
    if args.group_by == "TAG":
        group_def["Key"] = args.tag_key
    else:
        group_def["Key"] = args.group_by

    resp = ce.get_cost_and_usage(
        TimePeriod={"Start": args.start, "End": args.end},
        Granularity=args.granularity,
        Metrics=[args.metric],
        GroupBy=[group_def],
    )

    rows = []
    for period in resp["ResultsByTime"]:
        period_start = period["TimePeriod"]["Start"]
        for grp in period.get("Groups", []):
            key = "/".join(grp["Keys"])
            amount = grp["Metrics"][args.metric]["Amount"]
            unit = grp["Metrics"][args.metric]["Unit"]
            rows.append({"Period": period_start, "Group": key, "Amount": f"{float(amount):.4f}", "Unit": unit})
        if not period.get("Groups") and "Total" in period:
            amount = period["Total"].get(args.metric, {}).get("Amount", "0")
            unit = period["Total"].get(args.metric, {}).get("Unit", "USD")
            rows.append({"Period": period_start, "Group": "Total", "Amount": f"{float(amount):.4f}", "Unit": unit})

    app.out(rows)


@cost_grp.register("forecast", help="Show predicted future costs.", args=[
    arg("--start", default=date.today().isoformat(),
        help="Forecast start date."),
    arg("--end", default=(date.today() + timedelta(days=30)).isoformat(),
        help="Forecast end date."),
    choice("--granularity", ["DAILY", "MONTHLY"], default="MONTHLY"),
    choice("--metric", ["BLENDED_COST", "UNBLENDED_COST", "AMORTIZED_COST"],
           default="UNBLENDED_COST"),
])
def forecast(app: AppContext, args: argparse.Namespace) -> None:
    ce = app.client("ce", region="us-east-1")
    resp = ce.get_cost_forecast(
        TimePeriod={"Start": args.start, "End": args.end},
        Granularity=args.granularity,
        Metric=args.metric,
    )
    total = resp.get("Total", {})
    rows = [
        {"Period": p["TimePeriod"]["Start"], "MeanValue": f"{float(p['MeanValue']):.4f}"}
        for p in resp.get("ForecastResultsByTime", [])
    ]
    print(
        f"Total forecast: {float(total.get('Amount', 0)):.4f} {total.get('Unit', 'USD')}\n",
        file=sys.stderr,
    )
    app.out(rows)


@cost_grp.register("anomalies", help="Show cost anomalies detected by AWS Cost Explorer.",
                   args=[
                       arg("--days", type=int, default=14, help="Look-back window in days."),
                       arg("--min-impact", dest="min_impact", type=float, default=0.0,
                           help="Minimum total impact (USD)."),
                   ])
def anomalies(app: AppContext, args: argparse.Namespace) -> None:
    ce = app.client("ce", region="us-east-1")
    start = (date.today() - timedelta(days=args.days)).isoformat()
    end = date.today().isoformat()
    resp = ce.get_anomalies(
        DateInterval={"StartDate": start, "EndDate": end},
        TotalImpact={"NumericOperator": "GREATER_THAN_OR_EQUAL", "StartValue": args.min_impact},
    )
    rows = [
        {
            "AnomalyId": a["AnomalyId"],
            "Service": a.get("RootCauses", [{}])[0].get("Service", ""),
            "TotalImpact": f"{a.get('Impact', {}).get('TotalImpact', 0):.2f}",
            "StartDate": a.get("AnomalyStartDate", ""),
            "EndDate": a.get("AnomalyEndDate", "ongoing"),
        }
        for a in resp.get("Anomalies", [])
    ]
    app.out(rows or [{"msg": "No anomalies found in the specified period."}])


@cost_grp.register("rightsizing", help="Show rightsizing recommendations to reduce costs.",
                   args=[
                       arg("--service", default="AmazonEC2",
                           help="AWS service to get recommendations for."),
                   ])
def rightsizing(app: AppContext, args: argparse.Namespace) -> None:
    ce = app.client("ce", region="us-east-1")
    resp = ce.get_rightsizing_recommendation(Service=args.service)
    rows = [
        {
            "ResourceId": r.get("CurrentInstance", {}).get("ResourceId", ""),
            "CurrentType": r.get("CurrentInstance", {}).get("InstanceType", ""),
            "RecommendedType": r.get("RightsizingType", ""),
            "EstimatedMonthlySavings": r.get("ModifyRecommendationDetail", {})
            .get("TargetInstances", [{}])[0]
            .get("EstimatedMonthlySavings", ""),
        }
        for r in resp.get("RightsizingRecommendations", [])
    ]
    app.out(rows or [{"msg": "No rightsizing recommendations available."}])
