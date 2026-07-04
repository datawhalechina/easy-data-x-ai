"""
x1_1_decay_score_demo.py — 遗忘分数计算与分层倍率演示

本脚本直观展示 PowerMem 艾宾浩斯遗忘公式的计算过程:
  R = e^(-t / (24 * S))

其中强度 S = decay_rate × 层级倍率 × (1 + log(1 + access_count))

运行:
  python x1_1_decay_score_demo.py

输出观察点:
  - working/short_term/long_term 三层记忆在 1h/1d/7d/30d/90d 后的保留率差异
  - 长期层 vs 临时层在同时间下的保留率差距可达数倍
  - 访问强化: 同一条记忆被检索次数越多，衰减越慢

对应正文: X1-1 §1.2-1.3 "从经典公式到工程形式 / 强度 S 的三个因子"
"""

import math
from datetime import datetime, timedelta


# ============================================================
# PowerMem 核心参数（来源: ebbinghaus_algorithm.py）
# ============================================================

# λ (decay_rate): 全局衰减速率常数
# 值越大 → 所有记忆衰减越慢。PowerMem 默认 1.5，可通过配置文件覆盖
DEFAULT_DECAY_RATE = 1.5

# 层级倍率: 决定三层记忆的衰减速度差距
# working(临时层) 的强度是 1.5 × 1 = 1.5
# short_term(中期层) 的强度是 1.5 × 7 = 10.5
# long_term(长期层) 的强度是 1.5 × 60 = 90
# 长期层有效强度是临时层的 60 倍——这就是"永久记忆"和"临时笔记"的本质差距
DEFAULT_DECAY_RATE_MULTIPLIERS = {
    "working": 1,       # 临时层: 当前任务相关，衰减最快，几小时内就明显下降
    "short_term": 7,    # 中期层: 近期交互记忆，可维持数周到数月
    "long_term": 60,    # 长期层: 稳定事实和偏好，衰减极慢，接近"永久"
}

# 复习时的强化比例
# 每次回顾这条记忆后，保留率恢复: new = old + 0.3 × (1 - old)
DEFAULT_REINFORCEMENT_FACTOR = 0.3

# 模拟衰减计算的参考时间点（相当于"现在"）
NOW = datetime(2026, 2, 1, 12, 0, 0)


def calculate_strength(memory_type: str, access_count: int,
                       decay_rate: float = DEFAULT_DECAY_RATE) -> float:
    """
    计算记忆的「有效强度」S。

    S 是艾宾浩斯公式 R = e^(-t / (24*S)) 中控制衰减速度的核心参数。
    S 越大 → 分母 24*S 越大 → e^(-t/大数) 衰减越慢。

    参数:
      memory_type: "working" / "short_term" / "long_term"
                   决定从 DEFAULT_DECAY_RATE_MULTIPLIERS 中取哪个倍率
      access_count: 这条记忆历史上被检索命中的次数
                    log1p 将其转换为递增但收益递减的强化因子
      decay_rate:   全局 λ，默认 1.5

    返回:
      S = decay_rate × 层级倍率 × (1 + log(1 + access_count))
      - working:  S ≈ 1.5   (access_count=0 时)
      - long_term: S ≈ 90    (access_count=0 时)
    """
    multiplier = DEFAULT_DECAY_RATE_MULTIPLIERS[memory_type]
    reinforcement = math.log1p(access_count)
    return decay_rate * multiplier * (1 + reinforcement)


def calculate_retention(
    created_at: datetime,
    memory_type: str,
    access_count: int,
    current_time: datetime = NOW,
    decay_rate: float = DEFAULT_DECAY_RATE,
) -> float:
    """
    计算记忆在当前时刻的保留率 R ∈ [0.0, 1.0]。

    1.0 = 完全没衰减；< 0.3 = 视为"遗忘"。
    """
    hours_elapsed = (current_time - created_at).total_seconds() / 3600
    strength = calculate_strength(memory_type, access_count, decay_rate)
    retention = math.exp(-hours_elapsed / (24 * strength))
    return max(0.0, min(1.0, retention))


def _format_bar(value: float, width: int = 30) -> str:
    """把 [0,1] 数值转成 #.... 进度条"""
    filled = int(value * width)
    return "#" * filled + "." * (width - filled)


def main():
    print("=" * 90)
    print("X1-1 遗忘分数计算与分层倍率演示")
    print(f"全局 λ (decay_rate) = {DEFAULT_DECAY_RATE}")
    print(f"层级倍率 = {DEFAULT_DECAY_RATE_MULTIPLIERS}")
    print(f"模拟时间起点 NOW = {NOW.strftime('%Y-%m-%d %H:%M')}")
    print("=" * 90)

    # ============================================================
    # 第一部分：三层记忆在同一时间轴上的保留率对比
    # ============================================================
    print(f"\n{'─' * 90}")
    print("第一部分：三层记忆在同一时间轴上的保留率（access_count = 0）")
    print(f"{'─' * 90}")

    time_points = [
        ("1 小时", timedelta(hours=1)),
        ("1 天", timedelta(days=1)),
        ("7 天", timedelta(days=7)),
        ("30 天", timedelta(days=30)),
        ("90 天", timedelta(days=90)),
    ]

    print(f"\n  {'时间跨度':<10}", end="")
    for layer in ("working", "short_term", "long_term"):
        print(f"  {layer:<22}", end="")
    print()
    print(f"  {'-' * 80}")

    for label, delta in time_points:
        created = NOW - delta
        print(f"  {label:<10}", end="")
        for layer in ("working", "short_term", "long_term"):
            r = calculate_retention(created, layer, access_count=0)
            print(f"  {r:.4f} {_format_bar(r, 18)}", end="")
        print()

    r_work_30d = calculate_retention(NOW - timedelta(days=30), "working", 0)
    r_long_30d = calculate_retention(NOW - timedelta(days=30), "long_term", 0)
    r_work_90d = calculate_retention(NOW - timedelta(days=90), "working", 0)
    r_long_90d = calculate_retention(NOW - timedelta(days=90), "long_term", 0)
    print(f"\n  关键差距：")
    if r_work_30d > 1e-6:
        print(f"    - 30 天后临时层 R = {r_work_30d:.4f}，长期层 R = {r_long_30d:.4f}，"
              f"差距约 {r_long_30d / r_work_30d:.0f} 倍")
    else:
        print(f"    - 30 天后临时层 R ≈ 0（已遗忘），长期层 R = {r_long_30d:.4f}——"
              f"两者已不在同一数量级")
    print(f"    - 90 天后临时层 R = {r_work_90d:.4f}（已遗忘），"
          f"长期层 R = {r_long_90d:.4f}（仍可召回）")

    # ============================================================
    # 第二部分：访问强化效果——同一记忆被多次检索后曲线被"拉平"
    # ============================================================
    print(f"\n{'─' * 90}")
    print("第二部分：访问强化对长期层记忆的影响")
    print("  场景: 同一条 long_term 记忆，access_count 从 0 → 50，30 天后的保留率")
    print(f"{'─' * 90}")

    print(f"\n  {'访问次数':<10} {'强度 S':<12} {'30 天后 R':<12} {'曲线':<32}")
    print(f"  {'-' * 70}")
    for n in (0, 1, 3, 5, 10, 20, 50):
        s = calculate_strength("long_term", n)
        r = calculate_retention(NOW - timedelta(days=30), "long_term", n)
        print(f"  {n:<10} {s:<12.2f} {r:<12.4f} {_format_bar(r, 30)}")

    print(f"\n  观察：")
    print(f"    - access_count=0 时 S=90；access_count=50 时 S≈90×(1+log(51))≈444")
    print(f"    - 访问次数翻倍并不能让 S 翻倍——log1p 是收益递减的强化因子")
    print(f"    - 让一条记忆衰减更慢的最有效办法仍是把它写进更高层级，而非反复检索。")

    # ============================================================
    # 第三部分：层级选错，后果有多严重
    # ============================================================
    print(f"\n{'─' * 90}")
    print("第三部分：层级选错的代价——同一事实写入不同层级的 30 天命运")
    print(f"{'─' * 90}")
    fact = "用户对花生过敏"
    print(f"\n  假设事实「{fact}」被写入不同层级，30 天后的保留率：")
    for layer in ("working", "short_term", "long_term"):
        s = calculate_strength(layer, 0)
        r = calculate_retention(NOW - timedelta(days=30), layer, 0)
        bar = _format_bar(r, 30)
        verdict = "✓ 仍可召回" if r >= 0.3 else "✗ 已被遗忘"
        print(f"    {layer:<12} S={s:<7.1f} R={r:.4f} {bar}  {verdict}")

    print(f"\n  写入瞬间选错层级 = 决定了这条记忆能「活」多久。")
    print(f"  层级倍率 60 不是抽象参数，而是「长期事实」和「临时闲聊」之间数量级的差距。")
    print()


if __name__ == "__main__":
    main()
