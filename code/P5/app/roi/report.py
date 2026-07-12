"""Markdown, JSON, and CSV report generation for the ROI calculator."""

from __future__ import annotations

import csv
import json
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Iterable

from .models import RoiResult


def _number(value: Decimal | None, digits: int = 2) -> str:
    if value is None:
        return "不适用"
    quantizer = Decimal("1") if digits == 0 else Decimal("1." + "0" * digits)
    return f"{value.quantize(quantizer, rounding=ROUND_HALF_UP):,}"


def _money(value: Decimal | None, currency: str) -> str:
    return "不适用" if value is None else f"{currency} {_number(value)}"


def _percent(value: Decimal | None) -> str:
    return "不适用" if value is None else f"{_number(value)}%"


def _markdown(results: Iterable[RoiResult], currency: str, horizon_months: int) -> str:
    rows = list(results)
    lines = [
        "# AI Agent ROI 计算报告",
        "",
        f"计算口径：{horizon_months} 个月首年累计，币种：{currency}。",
        "",
        "## 情景对比",
        "",
        "| 情景 | 总成本 | 总收益 | 净收益 | ROI | 回收期（月） | 盈亏平衡任务量/月 | 状态 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for item in rows:
        lines.append(
            "| {scenario} | {cost} | {benefit} | {net} | {roi} | {payback} | {break_even} | {status} |".format(
                scenario=item.scenario,
                cost=_money(item.total_cost, currency),
                benefit=_money(item.total_benefit, currency),
                net=_money(item.net_benefit, currency),
                roi=_percent(item.roi_percent),
                payback=_number(item.payback_period_months),
                break_even=_number(item.break_even_monthly_task_volume, 0),
                status=item.status,
            )
        )

    lines.extend(["", "## 计算口径", ""])
    lines.extend(
        [
            "- 总成本 = 初始投入 + 12 ×（每月固定成本 + 每月任务量 × 单任务可变成本）。",
            "- 人力节省、收入提升、风险降低分别基于独立业务假设计算；请避免将同一业务效果重复计入多项收益。",
            "- ROI = （总收益 - 总成本）/ 总成本 × 100%。回收期仅在月净收益为正时计算。",
            "- 盈亏平衡任务量表示在首年口径下达到总净收益为零所需的每月任务量。",
        ]
    )
    for item in rows:
        lines.extend(["", f"## {item.scenario} 情景", "", item.description or "无额外说明。", ""])
        lines.extend(
            [
                f"- 初始投入：{_money(item.initial_cost, currency)}",
                f"- 每月固定成本：{_money(item.monthly_fixed_cost, currency)}",
                f"- 每月可变成本：{_money(item.monthly_variable_cost, currency)}",
                f"- 每月人力节省：{_money(item.monthly_human_saving, currency)}",
                f"- 每月收入提升：{_money(item.monthly_revenue_lift, currency)}",
                f"- 每月风险降低：{_money(item.monthly_risk_reduction, currency)}",
                f"- 每月独立效率收益：{_money(item.monthly_efficiency_gain, currency)}",
                f"- 每月净收益：{_money(item.monthly_net_benefit, currency)}",
            ]
        )
        if item.warnings:
            lines.extend(["", "注意："])
            lines.extend(f"- {warning}" for warning in item.warnings)
    return "\n".join(lines) + "\n"


def write_reports(
    results: Iterable[RoiResult], output_dir: str | Path, currency: str, horizon_months: int
) -> list[Path]:
    """Write stable report files and return their paths."""
    rows = list(results)
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)

    markdown_path = directory / "roi_report.md"
    json_path = directory / "roi_report.json"
    csv_path = directory / "scenario_comparison.csv"

    markdown_path.write_text(_markdown(rows, currency, horizon_months), encoding="utf-8")
    json_path.write_text(
        json.dumps(
            {
                "currency": currency,
                "horizon_months": horizon_months,
                "scenarios": [result.to_dict() for result in rows],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "scenario",
                "status",
                "currency",
                "horizon_months",
                "total_cost",
                "total_benefit",
                "net_benefit",
                "roi_percent",
                "payback_period_months",
                "break_even_monthly_task_volume",
            ],
        )
        writer.writeheader()
        for result in rows:
            writer.writerow(
                {
                    "scenario": result.scenario,
                    "status": result.status,
                    "currency": result.currency,
                    "horizon_months": result.horizon_months,
                    "total_cost": result.total_cost,
                    "total_benefit": result.total_benefit,
                    "net_benefit": result.net_benefit,
                    "roi_percent": result.roi_percent,
                    "payback_period_months": result.payback_period_months,
                    "break_even_monthly_task_volume": result.break_even_monthly_task_volume,
                }
            )
    return [markdown_path, json_path, csv_path]
