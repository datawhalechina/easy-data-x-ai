"""
x1_11_consolidation_passive.py — 被动巩固：高重要性直通长期层

本脚本演示记忆巩固的第一种触发方式: 被动触发 (写入时分流)。

PowerMem 的 _classify_memory_type 在写入瞬间完成分层:
  importance ≥ 0.8 → long_term (衰减倍率 ×60, 接近"永久记忆")
  0.6 ≤ importance < 0.8 → short_term (衰减倍率 ×7, 中等持久)
  importance < 0.6 → working (衰减倍率 ×1, 几天内自然淘汰)

运行:
  python x1_11_consolidation_passive.py

输出:
  - 6 条不同重要性的记忆各自进入哪个层级
  - 长期层 vs 临时层在写入后 1d/7d/30d/90d/365d 的衰减曲线对比
  - 被动巩固的局限性: 只能基于单条记忆, 无法发现"多条短期记忆凑一起=重要"的模式

对应正文: X1-3 §2.1 "被动触发：写入时的一次分流"
"""

import math
from datetime import datetime, timedelta


# PowerMem 源码参数
DECAY_RATE = 1.5
DECAY_RATE_MULTIPLIERS = {"working": 1, "short_term": 7, "long_term": 60}
LONG_TERM_THRESHOLD = 0.8
SHORT_TERM_THRESHOLD = 0.6
NOW = datetime(2026, 2, 1, 12, 0, 0)


def classify_memory_type(importance_score: float) -> str:
    """模拟 PowerMem _classify_memory_type"""
    if importance_score >= LONG_TERM_THRESHOLD:
        return "long_term"
    if importance_score >= SHORT_TERM_THRESHOLD:
        return "short_term"
    return "working"


def calculate_retention(
    created_at: datetime,
    memory_type: str,
    access_count: int,
    current_time: datetime = NOW,
) -> float:
    """计算保留率 R = e^(-t / (24*S))，t 为 created_at 到 current_time 的小时数"""
    hours_elapsed = (current_time - created_at).total_seconds() / 3600
    multiplier = DECAY_RATE_MULTIPLIERS[memory_type]
    reinforcement = math.log1p(access_count)
    strength = DECAY_RATE * multiplier * (1 + reinforcement)
    return max(0.0, min(1.0, math.exp(-hours_elapsed / (24 * strength))))


def main():
    print("=" * 85)
    print("X1-11 被动巩固：高重要性直通长期层")
    print(f"{'=' * 85}")

    # 不同重要性的记忆写入（带模拟的 access_count，让保留率更贴近真实场景）
    test_memories = [
        # (内容, 重要性, access_count) —— access_count 模拟「30 天里被检索过几次」
        ("用户对花生过敏，所有食物建议必须避开", 0.95, 8),
        ("用户是高级后端工程师，主力语言 Go，8 年经验", 0.85, 5),
        ("用户正在做的电商项目使用 Django + PostgreSQL", 0.72, 3),
        ("用户偏好简洁的代码风格，不喜欢过多注释", 0.65, 2),
        ("用户最近在考虑学习 Kubernetes", 0.55, 0),
        ("用户今天早上喝了咖啡", 0.20, 0),
    ]

    print(f"\n  重要性阈值: long_term ≥ {LONG_TERM_THRESHOLD}, "
          f"short_term ≥ {SHORT_TERM_THRESHOLD}")
    print(f"  写入时间: {NOW.strftime('%Y-%m-%d %H:%M')}")
    print(f"\n  {'内容':<50} {'重要性':<8} {'层级':<12} {'30天后保留率':<15}")
    print(f"  {'-' * 85}")

    consolidated = []  # 被巩固到长期层的记忆

    # 模拟"30 天后"再算保留率：把当前时间推到 30 天后
    future_now = NOW + timedelta(days=30)

    for content, importance, access in test_memories:
        mem_type = classify_memory_type(importance)
        # 被动巩固：写入瞬间就决定了层级
        created = NOW
        # 用 future_now 作为"当前时间"，算"写入后 30 天的保留率"
        retention_30d = calculate_retention(
            created, mem_type, access_count=access, current_time=future_now
        )

        marker = ""
        if mem_type == "long_term":
            marker = " * 直通长期层"
            consolidated.append(content)

        print(f"  {content:<50} {importance:<8.2f} {mem_type:<12} "
              f"{retention_30d:.4f} ({retention_30d*100:.1f}%){marker}")

    # 展示长期层 vs 临时层的衰减差异
    print(f"\n{'-' * 85}")
    print("长期层 vs 临时层：写入后各时间点的保留率对比")
    print(f"{'-' * 85}")

    time_points = [
        ("写入时", NOW),
        ("1 天后", NOW + timedelta(days=1)),
        ("7 天后", NOW + timedelta(days=7)),
        ("30 天后", NOW + timedelta(days=30)),
        ("90 天后", NOW + timedelta(days=90)),
        ("365 天后", NOW + timedelta(days=365)),
    ]

    def _bar(value: float, width: int = 15) -> str:
        filled = int(value * width)
        return "#" * filled + "." * (width - filled)

    print(f"\n  {'时间点':<15} {'长期层 (花生过敏)':<25} {'临时层 (喝咖啡)':<25}")
    print(f"  {'-' * 65}")
    for label, tp in time_points:
        r_long = calculate_retention(NOW, "long_term", 0, current_time=tp)
        r_work = calculate_retention(NOW, "working", 0, current_time=tp)
        print(f"  {label:<15} {r_long:.4f} {_bar(r_long):<15}  "
              f"{r_work:.4f} {_bar(r_work):<15}")

    # 用真实公式值替换之前硬编码的错误数字
    r_long_30d = calculate_retention(NOW, "long_term", 0, current_time=NOW + timedelta(days=30))
    r_long_90d = calculate_retention(NOW, "long_term", 0, current_time=NOW + timedelta(days=90))
    r_work_1d = calculate_retention(NOW, "working", 0, current_time=NOW + timedelta(days=1))
    r_work_7d = calculate_retention(NOW, "working", 0, current_time=NOW + timedelta(days=7))

    # 结论
    print(f"\n{'-' * 85}")
    print("关键观察")
    print(f"{'-' * 85}")
    print(f"  1. 写入瞬间完成分层：高重要性（≥{LONG_TERM_THRESHOLD}）直通长期层")
    print(f"  2. 长期层即使 access_count=0，30 天后 R ≈ {r_long_30d:.2f}，"
          f"90 天后仍有 R ≈ {r_long_90d:.2f}——安全关键信息能长期维持可召回状态")
    print(f"  3. 临时层 1 天后 R ≈ {r_work_1d:.2f}，7 天后 R ≈ {r_work_7d:.4f}——"
          f"低价值信息几天内即被自然淘汰")
    print(f"  4. 「对花生过敏」这种安全关键信息自动进入长期层，不会被快速遗忘")
    print(f"  5. 中期层若被频繁检索（access_count 高）可让 R 回升——这是访问强化的效果；")
    print(f"     但单纯靠访问无法把临时层升级到长期层的衰减速度")
    print(f"  6. 被动巩固的局限：只能基于单条记忆的重要性判断，")
    print(f"     无法发现「多条短期记忆隐含一个稳定事实」的模式 → 需要主动 reflection")
    print()


if __name__ == "__main__":
    main()
