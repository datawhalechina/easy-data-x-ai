# X1 实验代码

> 配套 [X1 探究 AI Agent 记忆系统：从遗忘曲线到永久记忆](../../docs/extra/X1%20探究%20AI%20Agent%20记忆系统：从遗忘曲线到永久记忆.md) 系列文章

## 环境要求

- Python 3.10+
- 无需 PowerMem 或 SeekDB 环境
- 所有实验使用纯 Python 标准库 + JSON fixtures，**无需 `pip install` 任何第三方包**

> 说明：本目录下的脚本用主题关键词字典模拟 embedding 相似度（避免引入 jieba / numpy / openai 等依赖）。生产环境中应替换为真实的向量检索。

## 配置

`.env.example` 仅为后续接入真实 embedding 服务时参考，当前 15 个脚本都不会调用任何外部 API。

## Windows 用户请注意中文编码

Windows 默认控制台是 GBK 编码，直接运行可能导致中文输出乱码。建议在终端先执行：

```bash
set PYTHONUTF8=1
# 或
set PYTHONIOENCODING=utf-8
```

PowerShell 用户：

```powershell
$env:PYTHONUTF8=1
```

之后再 `python xxx.py`，中文输出即可正常显示。

## 实验导航

### 上篇：记忆的生命周期工程（[`part1_decay_conflict/`](part1_decay_conflict/)）

| 脚本 | 说明 |
| --- | --- |
| `x1_1_decay_score_demo.py` | 遗忘分数计算与分层倍率演示 |
| `x1_2_decay_param_ablation.py` | λ / 归档阈值对比实验 |
| `x1_3_retrieval_with_decay.py` | 两阶段检索：粗筛 + 精排 |
| `x1_4_conflict_detect.py` | 冲突检测与路由 |
| `x1_5_conflict_resolve.py` | 双时态写入、版本失效 |
| `x1_6_retrieval_aggregate.py` | 确定性聚合 vs LLM 判断对比 |

### 中篇：记忆的边界与信任（[`part2_namespace/`](part2_namespace/)）

| 脚本 | 说明 |
| --- | --- |
| `x1_7_namespace_isolation.py` | 命名空间隔离验证 |
| `x1_8_promote_and_share.py` | 权限提升与共享 |
| `x1_9_cross_agent_query.py` | 查询构建阶段过滤 |
| `x1_10_concurrent_write.py` | 并发写入冲突 |

### 下篇：从记忆到认知（[`part3_consolidation/`](part3_consolidation/)）

| 脚本 | 说明 |
| --- | --- |
| `x1_11_consolidation_passive.py` | 高重要性直通长期层 |
| `x1_12_consolidation_reflection.py` | Reflection 蒸馏 |
| `x1_13_profile_vs_facts.py` | 画像 + 事实库组合检索 |
| `x1_14_experience_distill.py` | 情景记忆 → 经验三元组 |
| `x1_15_benchmark_runner.py` | 简易评测跑分 |
