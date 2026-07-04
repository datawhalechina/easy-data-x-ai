# 上篇实验：记忆的生命周期工程

配套 [X1-1 记忆的生命周期工程](../../../docs/extra/X1-1%20记忆的生命周期工程.md)

## 运行环境

- Python 3.10+
- 仅使用标准库（`math` / `json` / `datetime` 等），无需额外安装

## 实验列表

| 序号 | 脚本 | 对应正文节 | 核心观察 |
| --- | --- | --- | --- |
| 1 | `x1_1_decay_score_demo.py` | §1.2-1.3 | 三层记忆在不同时间跨度的保留率差异，访问强化效果 |
| 2 | `x1_2_decay_param_ablation.py` | §2.2 | λ 对误忘率和检索质量的影响 |
| 3 | `x1_3_retrieval_with_decay.py` | §3.1 | 两阶段检索：粗筛 + 精排，访问强化对检索排序的改变 |
| 4 | `x1_4_conflict_detect.py` | §4.1 | 主题相似度初筛 + 规则路由（ADD/UPDATE/DELETE） |
| 5 | `x1_5_conflict_resolve.py` | §4.2 | is_active 标记切换、版本链追溯 |
| 6 | `x1_6_retrieval_aggregate.py` | §4.3 | 确定性聚合与全量返回对比 |

## 数据说明

`fixtures/sample_memories.json` 包含：
- 12 条不同层级、不同时间的模拟记忆（覆盖 working / short_term / long_term）
- 5 个冲突测试用例（矛盾、并存、细化、时间演进）
- 4 个检索查询及预期答案
