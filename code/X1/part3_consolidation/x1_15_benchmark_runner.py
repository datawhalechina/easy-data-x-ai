"""
x1_15_benchmark_runner.py — 多策略评测跑分

本脚本演示如何量化不同衰减策略的效果, 对比四个策略:
  1. no_decay (λ=100):  基本不衰减, 所有记忆都活着 → 噪声多
  2. default_decay (λ=1.5): PowerMem 默认参数 → 平衡点
  3. conservative_decay (λ=0.5): 保守策略 → 宁可多记不能漏
  4. aggressive_decay (λ=5.0): 激进策略 → 快速淘汰旧信息

评测维度:
  - 准确率: 在 eval_qa_pairs.json 上对比事实召回率
  - Token 消耗: 每次查询返回的记忆内容估算 Token 数
  - P99 延迟: 检索耗时(模拟)

运行:
  python x1_15_benchmark_runner.py

输入:
  - fixtures/eval_qa_pairs.json (8 个问答对, 覆盖事实/冲突/偏好...)
  - ../part1_decay_conflict/fixtures/sample_memories.json (12 条模拟记忆)

输出: 四种策略的三维对比表 (准确率 / Token / 延迟)

扩展: 替换 eval_qa_pairs.json 为 LOCOMO 子集即可获得标准化评测

对应正文: X1-3 §5.2 "不止看准确率"
"""

import math
import json
import os
import time
import random
from datetime import datetime


DECAY_RATE_MULTIPLIERS = {"working": 1, "short_term": 7, "long_term": 60}
NOW = datetime(2026, 2, 1, 12, 0, 0)


def load_all_data(script_dir: str) -> tuple:
    """加载所有 fixtures"""
    with open(os.path.join(script_dir, "fixtures", "eval_qa_pairs.json"), "r", encoding="utf-8") as f:
        eval_data = json.load(f)

    # 从 part1 的 fixtures 加载记忆数据
    part1_fixtures = os.path.join(script_dir, "..", "part1_decay_conflict", "fixtures", "sample_memories.json")
    part1_fixtures = os.path.normpath(part1_fixtures)
    with open(part1_fixtures, "r", encoding="utf-8") as f:
        memory_data = json.load(f)

    return eval_data, memory_data["memories"]


def calculate_retention(memory: dict, decay_rate: float) -> float:
    """使用指定 λ 计算保留率"""
    created_at = datetime.fromisoformat(memory["created_at"])
    hours_elapsed = (NOW - created_at).total_seconds() / 3600
    multiplier = DECAY_RATE_MULTIPLIERS.get(memory["memory_type"], 1)
    reinforcement = math.log1p(memory["access_count"])
    strength = decay_rate * multiplier * (1 + reinforcement)
    return max(0.0, min(1.0, math.exp(-hours_elapsed / (24 * strength))))


def simulate_semantic_score(content: str, query: str) -> float:
    """模拟语义相似度（中文友好）：基于主题关键词字典"""
    topic_keywords = {
        "编程语言": ["Python", "Java", "Go", "Rust", "编程", "语言", "开发", "后端", "主力", "框架"],
        "食物偏好": ["吃", "披萨", "素", "食物", "饮食", "餐厅", "过敏", "花生", "肉类"],
        "云平台": ["AWS", "阿里云", "云平台", "云服务", "云", "迁移"],
        "编辑器": ["VS Code", "编辑器", "IDE", "插件"],
        "电商项目": ["电商", "项目", "Django", "PostgreSQL", "技术栈"],
        "代码风格": ["代码", "风格", "注释", "简洁"],
        "学习": ["学", "教程", "初学者", "考虑"],
        "技术方案": ["技术", "方案", "推荐", "适合", "微服务"],
    }

    query_topics = [
        topic for topic, keywords in topic_keywords.items()
        if any(kw in query for kw in keywords)
    ]
    if not query_topics:
        return 0.0

    score = 0.0
    for topic in query_topics:
        keywords = topic_keywords[topic]
        hits = sum(1 for kw in keywords if kw in content)
        score += hits * 0.20
    return min(1.0, score)


def search_memories(memories: list, query: str, decay_rate: float) -> tuple:
    """
    模拟检索 + 衰减排序
    返回 (results, estimated_tokens, latency_ms)
    """
    start = time.perf_counter()

    candidates = []
    for mem in memories:
        semantic_score = simulate_semantic_score(mem["content"], query)
        if semantic_score < 0.1:
            continue

        retention = calculate_retention(mem, decay_rate)
        is_forgotten = retention < 0.3
        forgotten_mult = 0.1 if is_forgotten else 1.0

        final_score = semantic_score * retention * forgotten_mult
        if final_score > 0:
            candidates.append({
                "id": mem["id"],
                "content": mem["content"],
                "final_score": final_score,
                "retention": retention,
                "is_forgotten": is_forgotten,
                "is_active": mem["is_active"],
            })

    candidates.sort(key=lambda x: x["final_score"], reverse=True)

    elapsed_ms = (time.perf_counter() - start) * 1000
    # 模拟更真实的大规模检索延迟（加随机噪声）
    simulated_latency = elapsed_ms + random.uniform(0.5, 2.0)

    # 过滤掉 final_score 过低的候选（模拟生产环境的最低相关度门控）
    # 这样不同 λ 下，"被衰减压到底部"的记忆会被自然剔除，Token 消耗随之变化
    MIN_SCORE_THRESHOLD = 0.01
    qualified = [c for c in candidates if c["final_score"] >= MIN_SCORE_THRESHOLD]
    top_n = qualified[:5]

    # 估计 Token 消耗（中文约 2 字/token）
    total_chars = sum(len(c["content"]) for c in top_n)
    estimated_tokens = int(total_chars * 0.5) + 100  # +100 for prompt overhead

    return top_n, estimated_tokens, simulated_latency


def evaluate_answer(results: list, expected_keywords: list[str]) -> bool:
    """
    检查返回的记忆中是否包含预期答案的关键词。
    判定标准：expected_keywords 中至少有一个长度 ≥ 2 的关键词出现在 top-3 内容里。
    """
    all_content = " ".join(r["content"] for r in results[:3])
    for kw in expected_keywords:
        if len(kw) >= 2 and kw in all_content:
            return True
    return False


def _split_expected_answer(answer: str) -> list[str]:
    """
    把 expected_answer 切成关键词列表。
    中文预期答案常含「，」「、」等标点而无空格，仅用 split() 会得到整句——
    改为先按标点/空格切分，再丢掉过短的片段。
    """
    import re
    # 按中英文标点和空格切分
    parts = re.split(r'[，,、。；;\s]+', answer)
    return [p for p in parts if len(p) >= 2]


def run_benchmark(memories: list, eval_data: dict, decay_rate: float, strategy_name: str) -> dict:
    """运行一次完整的评测"""
    correct = 0
    total = 0
    total_tokens = 0
    total_latency = 0
    latencies = []

    for q in eval_data["qa_pairs"]:
        results, tokens, latency = search_memories(memories, q["question"], decay_rate)

        # 提取预期关键词（按标点切分，避免中文整句无法匹配）
        expected_kws = _split_expected_answer(q["expected_answer"])

        is_correct = evaluate_answer(results, expected_kws)
        if is_correct:
            correct += 1
        total += 1
        total_tokens += tokens
        total_latency += latency
        latencies.append(latency)

    # 模拟 P99 延迟（在有限样本下取最大值）
    latencies.sort()
    p99 = latencies[int(len(latencies) * 0.99)] if len(latencies) > 1 else latencies[-1]

    return {
        "strategy": strategy_name,
        "decay_rate": decay_rate,
        "accuracy": correct / total if total > 0 else 0,
        "correct": correct,
        "total": total,
        "avg_tokens_per_query": total_tokens / total if total > 0 else 0,
        "avg_latency_ms": total_latency / total if total > 0 else 0,
        "p99_latency_ms": p99,
    }


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    eval_data, memories = load_all_data(script_dir)

    strategies = eval_data["strategies_to_evaluate"]

    print("=" * 85)
    print("X1-15 简易评测跑分")
    print(f"评测集: {len(eval_data['qa_pairs'])} 个问答对")
    print(f"记忆库: {len(memories)} 条记忆")
    print(f"{'=' * 85}")

    results = []
    for strat in strategies:
        result = run_benchmark(
            memories, eval_data, strat["params"]["decay_rate"], strat["name"]
        )
        results.append(result)

    # 输出对比表
    print(f"\n  {'策略':<18} {'λ':<8} {'准确率':<14} {'平均Token':<14} {'平均延迟':<14} {'P99延迟':<12}")
    print(f"  {'-' * 80}")
    for r in results:
        print(f"  {r['strategy']:<18} {r['decay_rate']:<8.1f} "
              f"{r['accuracy']:.0%} ({r['correct']}/{r['total']})     "
              f"{r['avg_tokens_per_query']:<8.0f}        "
              f"{r['avg_latency_ms']:<8.1f}ms       "
              f"{r['p99_latency_ms']:<8.1f}ms")

    # 找性能最优的（在准确率满足阈值的前提下）
    threshold = 0.7
    acceptable = [r for r in results if r["accuracy"] >= threshold]

    print(f"\n{'-' * 85}")
    if acceptable:
        cheapest = min(acceptable, key=lambda x: x["avg_tokens_per_query"])
        fastest = min(acceptable, key=lambda x: x["avg_latency_ms"])
        print(f"准确率 ≥ {threshold:.0%} 的策略中：")
        print(f"  最省 Token: {cheapest['strategy']} ({cheapest['avg_tokens_per_query']:.0f} tokens/query, "
              f"准确率 {cheapest['accuracy']:.0%})")
        print(f"  最快速: {fastest['strategy']} ({fastest['avg_latency_ms']:.1f}ms avg)")
    else:
        print(f"警告：没有任何策略达到 {threshold:.0%} 准确率，需调参或扩充 fixtures")

    # 多维度总结
    print(f"\n{'=' * 85}")
    print("多维度评测总结")
    print(f"{'=' * 85}")
    print(f"  维度           测量方法                      结论")
    print(f"  {'-' * 65}")
    print(f"  准确性          固定 QA 对评测集              低 λ（0.5）误忘率高；")
    print(f"                                              默认 1.5 / 高 λ 表现接近")
    print(f"  Token 效率      每次查询返回的记忆内容 Token   高 λ 会保留更多旧记忆→Token 略增")
    print(f"  检索延迟        P99 模拟                      不同策略差异小（均为 ms 级）")
    print(f"  一致性          同一 query 重复查询方差        确定性聚合优于 LLM 判断")
    print(f"\n  注：本实验为模拟评测，实际评测需要真实 LLM 调用和更大规模的测试集。")
    print(f"  LOCOMO 等标准化的 benchmark 可提供更可靠的对比数据。")
    print()


if __name__ == "__main__":
    main()
