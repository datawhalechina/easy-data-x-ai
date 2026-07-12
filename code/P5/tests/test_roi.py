from __future__ import annotations

import csv
import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from app.roi.calculator import calculate_scenario, load_config, run
from app.roi.models import ConfigError, Scenario


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "roi_scenarios.yaml"


class RoiCalculatorTest(unittest.TestCase):
    def test_base_scenario_matches_documented_first_year_example(self) -> None:
        currency, horizon, scenarios = load_config(CONFIG)
        base = next(item for item in scenarios if item.name == "base")
        result = calculate_scenario(base, currency, horizon)

        self.assertEqual(result.total_cost, Decimal("13600"))
        self.assertEqual(result.total_benefit, Decimal("22800"))
        self.assertEqual(result.net_benefit, Decimal("9200"))
        self.assertEqual(result.roi_percent, Decimal("67.64705882352941176470588235"))
        self.assertEqual(result.payback_period_months, Decimal("3.636363636363636363636363636"))
        self.assertEqual(result.break_even_monthly_task_volume, Decimal("52.08333333333333333333333333"))
        self.assertEqual(result.status, "profitable")

    def test_report_files_include_all_scenarios_in_stable_order(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            paths = run(CONFIG, directory)
            self.assertEqual({path.name for path in paths}, {"roi_report.md", "roi_report.json", "scenario_comparison.csv"})
            report = json.loads((Path(directory) / "roi_report.json").read_text(encoding="utf-8"))
            self.assertEqual([item["scenario"] for item in report["scenarios"]], ["conservative", "base", "optimistic"])
            with (Path(directory) / "scenario_comparison.csv").open(encoding="utf-8", newline="") as handle:
                self.assertEqual([row["scenario"] for row in csv.DictReader(handle)], ["conservative", "base", "optimistic"])

    def test_non_positive_monthly_net_benefit_has_no_payback(self) -> None:
        raw = {
            "description": "loss case",
            "metrics": {
                "monthly_task_count": 10,
                "agent_handoff_rate": 1,
                "agent_task_success_rate": 0,
                "agent_risk_event_rate": 1,
                "agent_variable_cost_per_task": 10,
            },
            "costs": {
                "data": {"initial_preparation_cost": 0, "monthly_maintenance_cost": 0},
                "model": {"initial_evaluation_cost": 0, "monthly_fixed_cost": 0},
                "business": {
                    "initial_integration_cost": 100,
                    "initial_training_cost": 0,
                    "monthly_operations_cost": 0,
                },
            },
            "business_baseline": {
                "baseline_human_handling_rate": 1,
                "human_cost_per_task": 1,
                "baseline_task_success_rate": 1,
                "value_per_incremental_successful_task": 1,
                "baseline_risk_event_rate": 0,
                "risk_loss_per_event": 1,
                "monthly_efficiency_gain": 0,
            },
        }
        result = calculate_scenario(Scenario.from_mapping("loss", raw))
        self.assertIsNone(result.payback_period_months)
        self.assertIsNone(result.break_even_monthly_task_volume)
        self.assertIn("月净收益不为正，项目无法回本。", result.warnings)

    def test_invalid_rate_is_rejected(self) -> None:
        with self.assertRaisesRegex(ConfigError, "agent_handoff_rate"):
            Scenario.from_mapping(
                "bad",
                {
                    "metrics": {
                        "monthly_task_count": 1,
                        "agent_handoff_rate": 1.2,
                        "agent_task_success_rate": 0,
                        "agent_risk_event_rate": 0,
                        "agent_variable_cost_per_task": 0,
                    },
                    "costs": {
                        "data": {"initial_preparation_cost": 0, "monthly_maintenance_cost": 0},
                        "model": {"initial_evaluation_cost": 0, "monthly_fixed_cost": 0},
                        "business": {
                            "initial_integration_cost": 0,
                            "initial_training_cost": 0,
                            "monthly_operations_cost": 0,
                        },
                    },
                    "business_baseline": {
                        "baseline_human_handling_rate": 1,
                        "human_cost_per_task": 0,
                        "baseline_task_success_rate": 0,
                        "value_per_incremental_successful_task": 0,
                        "baseline_risk_event_rate": 0,
                        "risk_loss_per_event": 0,
                        "monthly_efficiency_gain": 0,
                    },
                },
            )


if __name__ == "__main__":
    unittest.main()
