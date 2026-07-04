# 中篇实验：记忆的边界与信任

配套 [X1-2 记忆的边界与信任](../../../docs/extra/X1-2%20记忆的边界与信任.md)

## 运行环境

- Python 3.10+
- 仅使用标准库（`json` / `threading` / `time` 等），无需额外安装

## 实验列表

| 序号 | 脚本 | 对应正文节 | 核心观察 |
| --- | --- | --- | --- |
| 7 | `x1_7_namespace_isolation.py` | §1.1 | 默认隔离，Agent 互不可见 |
| 8 | `x1_8_promote_and_share.py` | §2.2 | promote 到 AGENT_GROUP 后同组可见，跨组仍不可见 |
| 9 | `x1_9_cross_agent_query.py` | §1.1 | 查询阶段过滤 vs 检索后过滤的延迟差 |
| 10 | `x1_10_concurrent_write.py` | §3.3 | 并发写冲突与乐观锁（CAS 重试） |
