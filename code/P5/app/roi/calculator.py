"""CLI entry point and financial calculations for the P5 ROI example."""

from __future__ import annotations

import argparse
from decimal import Decimal
from pathlib import Path
from typing import Any

import yaml

from .models import ConfigError, RoiResult, Scenario
from .report import write_reports


REQUIRED_SCENARIOS = ("conservative", "base", "optimistic")
DEFAULT_HORIZON_MONTHS = 12


def load_config(config_path: str | Path) -> tuple[str, int, list[Scenario]]:
    """Load a fixed-horizon ROI report configuration from YAML."""
    path = Path(config_path)
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ConfigError(f"cannot read config: {path}") from exc
    except yaml.YAMLError as exc:
        raise ConfigError(f"invalid YAML in {path}") from exc

    if not isinstance(raw, dict):
        raise ConfigError("config root must be a mapping")
    report = raw.get("report")
    if not isinstance(report, dict):
        raise ConfigError("report must be a mapping")
    currency = report.get("currency")
    if not isinstance(currency, str) or not currency.strip():
        raise ConfigError("report.currency must be a non-empty string")
    horizon = report.get("horizon_months")
    if horizon != DEFAULT_HORIZON_MONTHS:
        raise ConfigError("report.horizon_months must be 12 for the first-year ROI model")

    scenarios = raw.get("scenarios")
    if not isinstance(scenarios, dict):
        raise ConfigError("scenarios must be a mapping")
    missing = [name for name in REQUIRED_SCENARIOS if name not in scenarios]
    if missing:
        raise ConfigError(f"missing required scenarios: {', '.join(missing)}")
    return currency.strip(), horizon, [Scenario.from_mapping(name, scenarios[name]) for name in REQUIRED_SCENARIOS]


def calculate_scenario(scenario: Scenario, currency: str = "CNY", horizon_months: int = 12) -> RoiResult:
    """Calculate first-year costs, benefits, ROI, payback, and break-even volume."""
    months = Decimal(horizon_months)
    metrics = scenario.metrics
    costs = scenario.costs
    baseline = scenario.baseline

    initial_cost = (
        costs.data_initial_preparation
        + costs.model_initial_evaluation
        + costs.business_initial_integration
        + costs.business_initial_training
    )
    monthly_fixed_cost = (
        costs.data_monthly_maintenance + costs.model_monthly_fixed + costs.business_monthly_operations
    )
    monthly_variable_cost = metrics.monthly_task_count * metrics.agent_variable_cost_per_task
    total_cost = initial_cost + months * (monthly_fixed_cost + monthly_variable_cost)

    monthly_human_saving = (
        metrics.monthly_task_count
        * (baseline.baseline_human_handling_rate - metrics.agent_handoff_rate)
        * baseline.human_cost_per_task
    )
    monthly_revenue_lift = (
        metrics.monthly_task_count
        * (metrics.agent_task_success_rate - baseline.baseline_task_success_rate)
        * baseline.value_per_incremental_successful_task
    )
    monthly_risk_reduction = (
        metrics.monthly_task_count
        * (baseline.baseline_risk_event_rate - metrics.agent_risk_event_rate)
        * baseline.risk_loss_per_event
    )
    monthly_total_benefit = (
        monthly_human_saving
        + monthly_revenue_lift
        + monthly_risk_reduction
        + baseline.monthly_efficiency_gain
    )
    total_benefit = months * monthly_total_benefit
    net_benefit = total_benefit - total_cost
    monthly_net_benefit = monthly_total_benefit - monthly_fixed_cost - monthly_variable_cost

    warnings: list[str] = []
    roi_percent = None if total_cost == 0 else net_benefit / total_cost * Decimal("100")
    if roi_percent is None:
        warnings.append("总成本为 0，无法计算 ROI。")

    payback_period_months = None
    if monthly_net_benefit > 0:
        payback_period_months = initial_cost / monthly_net_benefit
        if payback_period_months > months:
            warnings.append("投资回收期超过首年计算周期。")
    else:
        warnings.append("月净收益不为正，项目无法回本。")

    benefit_per_task = (
        (baseline.baseline_human_handling_rate - metrics.agent_handoff_rate) * baseline.human_cost_per_task
        + (metrics.agent_task_success_rate - baseline.baseline_task_success_rate)
        * baseline.value_per_incremental_successful_task
        + (baseline.baseline_risk_event_rate - metrics.agent_risk_event_rate) * baseline.risk_loss_per_event
    )
    unit_margin = benefit_per_task - metrics.agent_variable_cost_per_task
    break_even_monthly_task_volume = None
    if unit_margin > 0:
        fixed_gap = initial_cost / months + monthly_fixed_cost - baseline.monthly_efficiency_gain
        break_even_monthly_task_volume = max(Decimal("0"), fixed_gap / unit_margin)
    else:
        warnings.append("单位任务边际收益不为正，没有可计算的盈亏平衡任务量。")

    if net_benefit > 0:
        status = "profitable"
    elif net_benefit < 0:
        status = "loss_making"
    else:
        status = "break_even"

    return RoiResult(
        scenario=scenario.name,
        description=scenario.description,
        currency=currency,
        horizon_months=horizon_months,
        initial_cost=initial_cost,
        monthly_fixed_cost=monthly_fixed_cost,
        monthly_variable_cost=monthly_variable_cost,
        total_cost=total_cost,
        monthly_human_saving=monthly_human_saving,
        monthly_revenue_lift=monthly_revenue_lift,
        monthly_risk_reduction=monthly_risk_reduction,
        monthly_efficiency_gain=baseline.monthly_efficiency_gain,
        monthly_total_benefit=monthly_total_benefit,
        total_benefit=total_benefit,
        net_benefit=net_benefit,
        roi_percent=roi_percent,
        monthly_net_benefit=monthly_net_benefit,
        payback_period_months=payback_period_months,
        break_even_monthly_task_volume=break_even_monthly_task_volume,
        status=status,
        warnings=tuple(warnings),
    )


def run(config_path: str | Path, output_dir: str | Path) -> list[Path]:
    """Run all required scenarios and return generated report paths."""
    currency, horizon, scenarios = load_config(config_path)
    results = [calculate_scenario(scenario, currency, horizon) for scenario in scenarios]
    return write_reports(results, output_dir, currency, horizon)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate the P5 first-year Agent ROI report.")
    parser.add_argument("--config", required=True, help="Path to the YAML scenario configuration.")
    parser.add_argument("--output-dir", default="outputs", help="Directory for Markdown, JSON, and CSV reports.")
    args = parser.parse_args(argv)

    try:
        paths = run(args.config, args.output_dir)
    except ConfigError as exc:
        parser.error(str(exc))
        return 2

    for path in paths:
        print(f"Generated: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
