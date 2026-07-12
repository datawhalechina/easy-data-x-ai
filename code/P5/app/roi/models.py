"""Validated input models and result serialization for the ROI calculator."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any


HUNDRED = Decimal("100")
TWELVE = Decimal("12")


class ConfigError(ValueError):
    """Raised when an ROI scenario has invalid business input."""


def _mapping(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ConfigError(f"{field} must be a mapping")
    return value


def _decimal(value: Any, field: str, *, minimum: Decimal | None = None) -> Decimal:
    if isinstance(value, bool):
        raise ConfigError(f"{field} must be a number")
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ConfigError(f"{field} must be a number") from exc
    if not number.is_finite():
        raise ConfigError(f"{field} must be finite")
    if minimum is not None and number < minimum:
        raise ConfigError(f"{field} must be greater than or equal to {minimum}")
    return number


def _rate(value: Any, field: str) -> Decimal:
    number = _decimal(value, field, minimum=Decimal("0"))
    if number > Decimal("1"):
        raise ConfigError(f"{field} must be between 0 and 1")
    return number


@dataclass(frozen=True)
class Metrics:
    monthly_task_count: Decimal
    agent_handoff_rate: Decimal
    agent_task_success_rate: Decimal
    agent_risk_event_rate: Decimal
    agent_variable_cost_per_task: Decimal

    @classmethod
    def from_mapping(cls, raw: Any, field: str = "metrics") -> "Metrics":
        data = _mapping(raw, field)
        task_count = _decimal(data.get("monthly_task_count"), f"{field}.monthly_task_count")
        if task_count <= 0:
            raise ConfigError(f"{field}.monthly_task_count must be greater than 0")
        return cls(
            monthly_task_count=task_count,
            agent_handoff_rate=_rate(data.get("agent_handoff_rate"), f"{field}.agent_handoff_rate"),
            agent_task_success_rate=_rate(
                data.get("agent_task_success_rate"), f"{field}.agent_task_success_rate"
            ),
            agent_risk_event_rate=_rate(
                data.get("agent_risk_event_rate"), f"{field}.agent_risk_event_rate"
            ),
            agent_variable_cost_per_task=_decimal(
                data.get("agent_variable_cost_per_task"),
                f"{field}.agent_variable_cost_per_task",
                minimum=Decimal("0"),
            ),
        )


@dataclass(frozen=True)
class LayerCosts:
    data_initial_preparation: Decimal
    data_monthly_maintenance: Decimal
    model_initial_evaluation: Decimal
    model_monthly_fixed: Decimal
    business_initial_integration: Decimal
    business_initial_training: Decimal
    business_monthly_operations: Decimal

    @classmethod
    def from_mapping(cls, raw: Any, field: str = "costs") -> "LayerCosts":
        data = _mapping(raw, field)
        data_costs = _mapping(data.get("data"), f"{field}.data")
        model_costs = _mapping(data.get("model"), f"{field}.model")
        business_costs = _mapping(data.get("business"), f"{field}.business")
        non_negative = Decimal("0")
        return cls(
            data_initial_preparation=_decimal(
                data_costs.get("initial_preparation_cost"),
                f"{field}.data.initial_preparation_cost",
                minimum=non_negative,
            ),
            data_monthly_maintenance=_decimal(
                data_costs.get("monthly_maintenance_cost"),
                f"{field}.data.monthly_maintenance_cost",
                minimum=non_negative,
            ),
            model_initial_evaluation=_decimal(
                model_costs.get("initial_evaluation_cost"),
                f"{field}.model.initial_evaluation_cost",
                minimum=non_negative,
            ),
            model_monthly_fixed=_decimal(
                model_costs.get("monthly_fixed_cost"),
                f"{field}.model.monthly_fixed_cost",
                minimum=non_negative,
            ),
            business_initial_integration=_decimal(
                business_costs.get("initial_integration_cost"),
                f"{field}.business.initial_integration_cost",
                minimum=non_negative,
            ),
            business_initial_training=_decimal(
                business_costs.get("initial_training_cost"),
                f"{field}.business.initial_training_cost",
                minimum=non_negative,
            ),
            business_monthly_operations=_decimal(
                business_costs.get("monthly_operations_cost"),
                f"{field}.business.monthly_operations_cost",
                minimum=non_negative,
            ),
        )


@dataclass(frozen=True)
class BusinessBaseline:
    baseline_human_handling_rate: Decimal
    human_cost_per_task: Decimal
    baseline_task_success_rate: Decimal
    value_per_incremental_successful_task: Decimal
    baseline_risk_event_rate: Decimal
    risk_loss_per_event: Decimal
    monthly_efficiency_gain: Decimal

    @classmethod
    def from_mapping(cls, raw: Any, field: str = "business_baseline") -> "BusinessBaseline":
        data = _mapping(raw, field)
        non_negative = Decimal("0")
        return cls(
            baseline_human_handling_rate=_rate(
                data.get("baseline_human_handling_rate"), f"{field}.baseline_human_handling_rate"
            ),
            human_cost_per_task=_decimal(
                data.get("human_cost_per_task"), f"{field}.human_cost_per_task", minimum=non_negative
            ),
            baseline_task_success_rate=_rate(
                data.get("baseline_task_success_rate"), f"{field}.baseline_task_success_rate"
            ),
            value_per_incremental_successful_task=_decimal(
                data.get("value_per_incremental_successful_task"),
                f"{field}.value_per_incremental_successful_task",
                minimum=non_negative,
            ),
            baseline_risk_event_rate=_rate(
                data.get("baseline_risk_event_rate"), f"{field}.baseline_risk_event_rate"
            ),
            risk_loss_per_event=_decimal(
                data.get("risk_loss_per_event"), f"{field}.risk_loss_per_event", minimum=non_negative
            ),
            monthly_efficiency_gain=_decimal(
                data.get("monthly_efficiency_gain"),
                f"{field}.monthly_efficiency_gain",
                minimum=non_negative,
            ),
        )


@dataclass(frozen=True)
class Scenario:
    name: str
    description: str
    metrics: Metrics
    costs: LayerCosts
    baseline: BusinessBaseline

    @classmethod
    def from_mapping(cls, name: str, raw: Any) -> "Scenario":
        data = _mapping(raw, f"scenarios.{name}")
        description = data.get("description", "")
        if not isinstance(description, str):
            raise ConfigError(f"scenarios.{name}.description must be a string")
        prefix = f"scenarios.{name}"
        return cls(
            name=name,
            description=description,
            metrics=Metrics.from_mapping(data.get("metrics"), f"{prefix}.metrics"),
            costs=LayerCosts.from_mapping(data.get("costs"), f"{prefix}.costs"),
            baseline=BusinessBaseline.from_mapping(data.get("business_baseline"), f"{prefix}.business_baseline"),
        )


@dataclass(frozen=True)
class RoiResult:
    scenario: str
    description: str
    currency: str
    horizon_months: int
    initial_cost: Decimal
    monthly_fixed_cost: Decimal
    monthly_variable_cost: Decimal
    total_cost: Decimal
    monthly_human_saving: Decimal
    monthly_revenue_lift: Decimal
    monthly_risk_reduction: Decimal
    monthly_efficiency_gain: Decimal
    monthly_total_benefit: Decimal
    total_benefit: Decimal
    net_benefit: Decimal
    roi_percent: Decimal | None
    monthly_net_benefit: Decimal
    payback_period_months: Decimal | None
    break_even_monthly_task_volume: Decimal | None
    status: str
    warnings: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        def value(number: Decimal | None) -> float | None:
            return None if number is None else float(number)

        return {
            "scenario": self.scenario,
            "description": self.description,
            "currency": self.currency,
            "horizon_months": self.horizon_months,
            "status": self.status,
            "costs": {
                "initial_cost": value(self.initial_cost),
                "monthly_fixed_cost": value(self.monthly_fixed_cost),
                "monthly_variable_cost": value(self.monthly_variable_cost),
                "total_cost": value(self.total_cost),
            },
            "benefits": {
                "monthly_human_saving": value(self.monthly_human_saving),
                "monthly_revenue_lift": value(self.monthly_revenue_lift),
                "monthly_risk_reduction": value(self.monthly_risk_reduction),
                "monthly_efficiency_gain": value(self.monthly_efficiency_gain),
                "monthly_total_benefit": value(self.monthly_total_benefit),
                "total_benefit": value(self.total_benefit),
            },
            "financials": {
                "net_benefit": value(self.net_benefit),
                "roi_percent": value(self.roi_percent),
                "monthly_net_benefit": value(self.monthly_net_benefit),
                "payback_period_months": value(self.payback_period_months),
                "break_even_monthly_task_volume": value(self.break_even_monthly_task_volume),
            },
            "warnings": list(self.warnings),
        }
