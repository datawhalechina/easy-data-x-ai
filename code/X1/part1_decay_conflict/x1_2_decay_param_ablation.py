"""
x1_2_decay_param_ablation.py — λ / 归档阈值消融实验

本脚本回答一个问题: decay_rate (λ) 该设为多少？

方法: 在同一批记忆上，依次用 λ = 0.5 / 1.0 / 1.5 / 3.0 / 5.0 跑衰减计算，
      对比每种 λ 下「保留率分布」和「误忘率」(高重要性记忆被错误淘汰的比例)。

运行:
  python x1_2_decay_param_ablation.py

输入: fixtures/sample_memories.json (12 条不同层级和重要性的模拟记忆)
输出:
  - 每种 λ 下的保留记忆数 vs 遗忘记忆数
  - 误忘计数 (importance_score ≥ 0.8 但 retention < 0.3 的记忆)
  - 逐条记忆在不同 λ 下的保留率详情
  - 推荐 λ 值

关键参数:
  archive_threshold = 0.3: 保留率低于此值视为"遗忘"
  λ 的选择需要在"噪声控制"和"误忘防止"之间取得平衡:
  - λ < 1.0: 保守，几乎不遗忘，检索质量下降
  - λ = 1.5: PowerMem 默认值，平衡点
  - λ > 3.0: 激进，快速淘汰，可能误忘重要信息

对应正文: X1-1 §2.2 "λ 怎么选：用同一批数据做对比"
"""

import math
import json
import os
from datetime import datetime, timedelta


DEFAULT_DECAY_RATE_MULTIPLIERS = {
    "working": 1,
    "short_term": 7,
    "long_term": 60,
}
NOW = datetime(2026, 2, 1, 12, 0, 0)


def calculate_retention(
    created_at: datetime,
    memory_type: str,     # "working" / "short_term" / "long_term", 决定衰减倍率
    access_count: int,    # 历史访问次数, 用于 log1p 强化因子
    decay_rate: float,    # 此次消融实验的 λ 值
) -> float:
    """
    使用指定的 λ 值计算保留率 R = e^(-t / (24*S))。
    与 x1_1 中的同名函数逻辑一致, 但 decay_rate 是参数而非全局常量。
    """
    # t: 从创建到当前(2026-02-01)的小时数
    hours_elapsed = (NOW - created_at).total_seconds() / 3600

    # 层级倍率: working=1, short_term=7, long_term=60
    multiplier = DEFAULT_DECAY_RATE_MULTIPLIERS.get(memory_type, 1)

    # 访问强化: log(1 + access_count), 访问越多衰减越慢
    reinforcement = math.log1p(access_count)

    # S = λ × 层级倍率 × (1 + 访问强化)
    strength = decay_rate * multiplier * (1 + reinforcement)

    # R = e^(-t / (24*S)), clamp 到 [0, 1]
    return max(0.0, min(1.0, math.exp(-hours_elapsed / (24 * strength))))


def load_memories(filepath: str) -> list:
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data["memories"]


def run_ablation(memories: list, lambdas: list[float], archive_threshold: float = 0.3):
    """运行消融实验"""
    results = []
    for lam in lambdas:
        retained = 0
        forgotten = 0
        forgotten_important = 0  # 误忘计数（重要性 ≥ 0.8 但保留率 < 阈值）
        total_importance_high = 0

        for mem in memories:
            ct = datetime.fromisoformat(mem["created_at"])
            r = calculate_retention(ct, mem["memory_type"], mem["access_count"], lam)

            if r >= archive_threshold:
                retained += 1
            else:
                forgotten += 1
                if mem["importance_score"] >= 0.8:
                    forgotten_important += 1

            if mem["importance_score"] >= 0.8:
                total_importance_high += 1

        total = len(memories)
        miss_rate = forgotten_important / total_importance_high if total_importance_high > 0 else 0

        results.append({
            "lambda": lam,
            "retained": retained,
            "forgotten": forgotten,
            "retention_ratio": retained / total,
            "forgotten_important": forgotten_important,
            "total_important": total_importance_high,
            "miss_rate": miss_rate,
        })
    return results


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    fixtures_path = os.path.join(script_dir, "fixtures", "sample_memories.json")

    memories = load_memories(fixtures_path)

    lambdas = [0.5, 1.0, 1.5, 2.0, 3.0, 5.0]
    archive_threshold = 0.3

    print("=" * 85)
    print("X1-2 λ 消融实验")
    print(f"模拟时间: {NOW.strftime('%Y-%m-%d')}")
    print(f"归档阈值: {archive_threshold}（保留率低于此值视为遗忘）")
    print(f"记忆总数: {len(memories)}")
    print("=" * 85)

    results = run_ablation(memories, lambdas, archive_threshold)

    print(f"\n{'λ':<8} {'保留':<6} {'遗忘':<6} {'保留率':<10} {'误忘高价值':<12} {'误忘率':<10}")
    print("-" * 85)
    for r in results:
        print(f"  {r['lambda']:<8} {r['retained']:<6} {r['forgotten']:<6} "
              f"{r['retention_ratio']:.2%}       {r['forgotten_important']}/{r['total_important']:<8}     {r['miss_rate']:.2%}")

    # 详细展开：每条记忆在不同 λ 下的保留率
    print(f"\n{'=' * 85}")
    print("逐条记忆保留率详情")
    print(f"{'=' * 85}")

    for mem in memories:
        ct = datetime.fromisoformat(mem["created_at"])
        print(f"\n  [{mem['id']}] {mem['content'][:60]}...")
        print(f"    类型={mem['memory_type']}, 重要性={mem['importance_score']}, "
              f"访问次数={mem['access_count']}, 距今={(NOW - ct).days} 天")
        print(f"    {'λ=0.5':<10} {'λ=1.0':<10} {'λ=1.5':<10} {'λ=2.0':<10} {'λ=3.0':<10} {'λ=5.0':<10}")
        retain_vals = []
        for lam in lambdas:
            r = calculate_retention(ct, mem["memory_type"], mem["access_count"], lam)
            retain_vals.append(f"{r:.4f}")
        print(f"    {'  '.join(retain_vals)}")

    # 重点标注误忘案例
    print(f"\n{'=' * 85}")
    print("误忘风险分析（归档阈值 = 0.3）")
    print(f"{'=' * 85}")
    for lam in lambdas:
        risky = []
        for mem in memories:
            ct = datetime.fromisoformat(mem["created_at"])
            r = calculate_retention(ct, mem["memory_type"], mem["access_count"], lam)
            if mem["importance_score"] >= 0.8 and r < archive_threshold:
                risky.append((mem["id"], mem["content"][:50], r))
        if risky:
            print(f"\n  λ={lam} 时，以下高价值记忆会被误忘：")
            for mid, content, r in risky:
                print(f"    [!] {mid}: {content}... (保留率={r:.4f})")
        else:
            print(f"\n  λ={lam}: 无高价值记忆被误忘")

    # 推荐结论
    print(f"\n{'=' * 85}")
    print("分析结论")
    print(f"{'=' * 85}")
    best = min(results, key=lambda x: abs(x["retention_ratio"] - 0.75))
    first_zero_miss = next((r["lambda"] for r in results if r["miss_rate"] == 0), None)
    print(f"  若目标保留率约 75%，推荐 λ ≈ {best['lambda']}")
    if first_zero_miss is not None:
        # 公式：λ 越大 → S 越大 → 衰减越慢 → 误忘越少
        # 所以「零误忘」应取 λ ≥ first_zero_miss
        print(f"  若对数据安全要求高（零误忘），建议 λ ≥ {first_zero_miss}")
    else:
        print(f"  当前 λ 区间内仍有误忘，建议进一步增大 λ 或下调归档阈值")
    print(f"  注意：λ 的选择还需结合检索准确率综合评估（见 x1_3）")
    print()


if __name__ == "__main__":
    main()
