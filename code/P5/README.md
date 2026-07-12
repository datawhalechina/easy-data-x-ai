# P5：AI Agent ROI 计算模型

本示例将企业知识库客服 Agent 的运行快照和业务假设，转换为首年累计的成本、收益、ROI、投资回收期和盈亏平衡任务量。

首期使用 YAML 示例快照，不依赖模型 API、Prometheus、LangSmith 或 Harbor。后续接入监控系统时，只需用真实的月任务量、转人工率、任务成功率、风险事件率和单任务成本替换配置值。

## 运行

要求 Python 3.10+。

```bash
cd code/P5
pip install -r requirements.txt
python -m app.roi.calculator --config config/roi_scenarios.yaml --output-dir outputs
```

命令生成：

```text
outputs/roi_report.md
outputs/roi_report.json
outputs/scenario_comparison.csv
```

这是一条**批量对比命令**：它会在一次运行中读取配置内的保守、基准、乐观三种情景，并同时写入三种报告。无需为每个情景分别执行命令。

运行测试：

```bash
python -m unittest discover -s tests -v
```

## 配置口径

`roi_scenarios.yaml` 固定包含 `conservative`、`base`、`optimistic` 三种情景，每个情景包含：

* `metrics`：月任务量、转人工率、任务成功率、风险事件率、单任务可变成本；
* `costs.data`、`costs.model`、`costs.business`：数据、模型、业务三层的初始和月度投入；
* `business_baseline`：人工处理、任务成功和风险事件的基线，以及业务价值假设。

计算周期固定为 12 个月，币种由 `report.currency` 指定。所有比例必须介于 `0` 与 `1`，金额不能为负，月任务量必须大于 `0`。

### 三种情景说明

示例配置不是只计算一个“默认场景”，而是用同一套成本和收益公式比较不同的运营预期：

| 情景 | 月任务量 | 转人工率 | 任务成功率 | 单任务成本 | 首年 ROI | 含义 |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `conservative`（保守） | 80 | 35% | 68% | 2.5 元 | -24.46% | 业务量低、转人工和模型调用成本较高 |
| `base`（基准） | 100 | 20% | 80% | 2 元 | 67.65% | 课程案例的预期运营水平 |
| `optimistic`（乐观） | 140 | 12% | 88% | 1.6 元 | 188.92% | 业务量增长，Agent 质量和调用成本持续改善 |

运行后优先查看 `outputs/scenario_comparison.csv` 或 `outputs/roi_report.md` 中的横向对比；`roi_report.json` 适合被其他程序继续读取。以上结果来自仓库内的示例假设，不应直接视为真实业务预测。

## 公式

```text
总成本（Total Cost, TotalCost）
  = 初始投入（Initial Cost, InitialCost）
  + 12 × [月固定成本（Monthly Fixed Cost, MonthlyFixedCost）
          + 月可变成本（Monthly Variable Cost, MonthlyVariableCost）]

总收益（Total Benefit, TotalBenefit）
  = 12 × [人力节省（Human Saving, HumanSaving）
          + 收入提升（Revenue Lift, RevenueLift）
          + 风险损失降低（Risk Reduction, RiskReduction）
          + 独立效率收益（Efficiency Gain, EfficiencyGain）]

净收益（Net Benefit, NetBenefit）= 总收益 - 总成本
投资回报率（Return on Investment, ROI）= 净收益 / 总成本 × 100%
```

| 中文术语 | 英文术语 | 报告字段 | 说明 |
| --- | --- | --- | --- |
| 总成本 | Total Cost | `total_cost` | 首年初始投入、固定成本和任务可变成本之和 |
| 总收益 | Total Benefit | `total_benefit` | 首年人力、收入、风险和独立效率收益之和 |
| 净收益 | Net Benefit | `net_benefit` | 总收益减去总成本 |
| 投资回报率 | Return on Investment | `roi_percent` | 净收益占总成本的比例 |
| 投资回收期 | Payback Period | `payback_period_months` | 初始投入被月净收益覆盖所需的月数 |
| 盈亏平衡任务量 | Break-even Monthly Task Volume | `break_even_monthly_task_volume` | 首年净收益为零所需的每月任务量 |

人力节省、收入提升和风险降低使用不同的业务假设。知识覆盖率、检索命中率和回答准确率是诊断指标，不能各自折算收益后直接相加；只有它们带来的人工处理、成功任务或风险事件变化才进入 ROI。
