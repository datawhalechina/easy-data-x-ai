"""
x1_9_cross_agent_query.py — 查询构建阶段过滤 vs 检索后过滤

两种实现命名空间隔离的方式, 在性能、安全和正确性上有本质差异:
  A. 查询阶段过滤 (PowerMem 采用): WHERE 子句直接注入 user_id + agent_id
     → 数据库索引层过滤，无关数据不离开数据库，延迟低
  B. 检索后过滤: 全量搜索 → 应用代码中筛掉不属于当前 namespace 的数据
     → 大量无效数据被拉到应用层再丢弃，延迟高且可能泄漏到日志

运行:
  python x1_9_cross_agent_query.py

输出:
  - 多规模 (100 ~ 10000 条) 下两种策略的耗时对比
  - 正确性验证: 两种策略结果是否一致
  - 安全性对比: 哪种方式更不容易泄漏敏感数据

对应正文: X1-2 §1.1 "命名空间：三个字段决定谁能看到什么"
"""

import json
import os
import time
import random
from datetime import datetime


def create_test_data(num_memories: int = 1000, num_agents: int = 10) -> list:
    """生成大规模测试数据"""
    memories = []
    topics = ["编程", "饮食", "健康", "旅行", "财务", "音乐", "运动", "读书", "游戏", "摄影"]
    for i in range(num_memories):
        topic = random.choice(topics)
        agent_idx = random.randint(0, num_agents - 1)
        memories.append({
            "id": f"mem_{i:05d}",
            "content": f"用户{topic}相关的偏好或事实 #{i}",
            "user_id": "user_001",
            "agent_id": f"agent_{agent_idx:02d}",
            "topic": topic,
            "is_active": True,
        })
    return memories


def filter_at_query_time(memories: list, user_id: str, agent_id: str, query: str) -> tuple:
    """
    查询构建阶段过滤（PowerMem 的方式）。
    WHERE 条件在搜索前已确定，搜索只命中目标子集。
    """
    start = time.perf_counter()

    # 模拟：先过滤再搜索（实际是 WHERE 子句直接限制索引范围）
    filtered = [m for m in memories if m["user_id"] == user_id and m["agent_id"] == agent_id]

    # 在过滤后的子集上搜索
    results = []
    for m in filtered:
        if any(kw in m["content"] for kw in query.split()):
            results.append(m)

    elapsed = time.perf_counter() - start
    return results, elapsed, len(filtered)


def filter_after_retrieval(memories: list, user_id: str, agent_id: str, query: str) -> tuple:
    """
    检索后过滤（不推荐的方式）。
    先全量搜索，再从结果中过滤不属于当前 namespace 的。
    """
    start = time.perf_counter()

    # 全量搜索
    all_results = []
    for m in memories:
        if any(kw in m["content"] for kw in query.split()):
            all_results.append(m)

    # 再过滤
    results = [m for m in all_results
               if m["user_id"] == user_id and m["agent_id"] == agent_id]

    elapsed = time.perf_counter() - start
    return results, elapsed, len(all_results)


def main():
    print("=" * 85)
    print("X1-9 查询构建阶段过滤 vs 检索后过滤")
    print(f"{'=' * 85}")

    scales = [100, 500, 1000, 5000, 10000]
    target_agent = "agent_05"
    user_id = "user_001"
    query = "编程 偏好"

    print(f"\n  目标 Agent: {target_agent}")
    print(f"  查询: 「{query}」")
    print(f"\n  {'规模':<10} {'策略':<20} {'搜索子集':<10} {'耗时':<15} {'结果数':<8}")
    print(f"  {'-' * 65}")

    for scale in scales:
        memories = create_test_data(scale, num_agents=10)

        # 策略 1：查询阶段过滤
        results1, elapsed1, subset_size = filter_at_query_time(
            memories, user_id, target_agent, query
        )

        # 策略 2：检索后过滤
        results2, elapsed2, full_search_size = filter_after_retrieval(
            memories, user_id, target_agent, query
        )

        speedup = elapsed2 / elapsed1 if elapsed1 > 0 else float("inf")

        print(f"  {scale:<10} {'查询阶段过滤':<20} {subset_size}/{scale:<7} "
              f"{elapsed1*1000:8.3f}ms  {len(results1):<8}")
        print(f"  {'':10} {'检索后过滤':<20} {full_search_size}/{scale:<7} "
              f"{elapsed2*1000:8.3f}ms  {len(results2):<8} "
              f"(×{speedup:.1f})")

    # 正确性验证
    print(f"\n{'-' * 85}")
    print("正确性验证（规模=1000）")
    print(f"{'-' * 85}")
    test_data = create_test_data(1000, num_agents=10)
    r1, _, _ = filter_at_query_time(test_data, user_id, target_agent, "编程")
    r2, _, _ = filter_after_retrieval(test_data, user_id, target_agent, "编程")

    ids1 = set(m["id"] for m in r1)
    ids2 = set(m["id"] for m in r2)
    if ids1 == ids2:
        print(f"  [v] 两种策略结果一致（{len(ids1)} 条）")
    else:
        print(f"  [!] 结果不一致！差异: {ids1 ^ ids2}")

    # 安全性对比
    print(f"\n{'-' * 85}")
    print("安全性对比")
    print(f"{'-' * 85}")
    print(f"  查询阶段过滤：")
    print(f"    → 不属于当前 namespace 的数据从未离开数据库")
    print(f"    → 即使日志记录查询语句，也不会泄漏其他 Agent 的数据")
    print(f"  检索后过滤：")
    print(f"    → 全量搜索结果经过应用层，可能被日志、异常堆栈捕获")
    print(f"    → 如果过滤代码有 bug，敏感数据可能意外返回给调用方")
    print(f"  结论：查询构建阶段过滤是安全基础，不是性能优化。")
    print()


if __name__ == "__main__":
    main()
