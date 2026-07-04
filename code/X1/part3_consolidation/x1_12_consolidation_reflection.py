"""
x1_12_consolidation_reflection.py — Reflection 蒸馏：从多条短期记忆中发现稳定事实

本脚本演示记忆巩固的第二种触发方式: 主动触发 (周期性 reflection)。

与 x1_11 的被动巩固不同, reflection 不看单条记忆的重要性, 而是扫描近期记忆,
发现"多条短期记忆凑在一起隐含一个重要事实"的模式:
  例: "看 Rust 教程" + "问生命周期问题" + "搭建 Rust 环境"
      → 蒸馏为 "用户正在系统学习 Rust, 是初学者"

运行:
  python x1_12_consolidation_reflection.py

输入: fixtures/reflection_input.json (10 条近期记忆, 覆盖 4 个话题)
输出:
  - 按话题分组的结果 ("Rust 学习" 5 条, "Python 开发" 2 条...)
  - 每个话题的蒸馏结果和置信度
  - 压缩比: 原始记忆数 vs 蒸馏后长期事实数
  - 置信度未达标的记忆保留在中期层, 等待更多证据

关键参数:
  min_count = 3: 至少 3 条相关记忆才能触发蒸馏 (避免单条孤证)
  min_confidence = 0.7: 置信度达标才写入长期层

对应正文: X1-3 §2.2 "主动触发：Reflection 蒸馏"
"""

import json
import os
from datetime import datetime, timedelta
from collections import defaultdict


NOW = datetime(2026, 2, 1, 12, 0, 0)


def group_by_topic(memories: list) -> dict:
    """按话题关键词分组"""
    topic_keywords = {
        "Rust 学习": ["Rust", "rustup", "Axum", "Actix", "ownership", "lifetime"],
        "Python 开发": ["Python", "Django", "pandas", "ORM", "CSV"],
        "生活习惯": ["跑步", "晨跑", "早起", "运动"],
        "饮食偏好": ["素食", "披萨", "餐厅", "饮食"],
    }

    groups = defaultdict(list)
    for mem in memories:
        for topic, keywords in topic_keywords.items():
            if any(kw in mem["content"] for kw in keywords):
                groups[topic].append(mem)
                break
        else:
            groups["其他"].append(mem)

    return dict(groups)


def reflection_analyze(
    topic: str,
    memories: list,
    min_count: int = 3,
    min_confidence: float = 0.7,
) -> dict | None:
    """
    模拟 LLM reflection：分析同一话题的多条记忆，蒸馏为稳定事实。

    实际系统中这一步骤由 LLM 完成：
    "以下是用户最近关于 {topic} 的记忆：[memories]
     请判断这些记忆是否隐含一个稳定的用户事实或偏好。
     如果是，用一句话总结。"

    这里用规则模拟 LLM 的输出。

    参数:
      min_count: 至少几条相关记忆才触发蒸馏
      min_confidence: 置信度阈值，达到才标记 consolidate_to_long_term
    """
    if len(memories) < min_count:
        return None

    # 模拟 LLM 蒸馏逻辑
    patterns = {
        "Rust 学习": {
            "keywords_check": ["教程", "环境", "框架", "教程", "API"],
            "distilled_fact": "用户正在系统学习 Rust 语言，已搭建开发环境并使用 Axum 框架实践，目前处于初学者阶段",
            "confidence": 0.85,
            "supporting_evidence": len(memories),
        },
        "Python 开发": {
            "keywords_check": ["Django", "Python", "ORM"],
            "distilled_fact": "用户具备 Django 开发能力，能独立处理 ORM 优化和大数据量导入",
            "confidence": 0.75,
            "supporting_evidence": len(memories),
        },
        "生活习惯": {
            "keywords_check": ["跑步", "晨跑"],
            "distilled_fact": "用户坚持每天晨跑，已形成稳定习惯",
            "confidence": 0.70 if len(memories) >= 3 else 0.40,
            "supporting_evidence": len(memories),
        },
        "饮食偏好": {
            "keywords_check": ["素食", "餐厅"],
            "distilled_fact": "用户持续尝试素食，偏好素食披萨等创意素食",
            "confidence": 0.65 if len(memories) >= 2 else 0.35,
            "supporting_evidence": len(memories),
        },
    }

    if topic in patterns:
        p = patterns[topic]
        confidence = p["confidence"]
        return {
            "topic": topic,
            "distilled_fact": p["distilled_fact"],
            "confidence": confidence,
            "supporting_count": len(memories),
            "source_memories": [m["id"] for m in memories],
            "action": "consolidate_to_long_term" if confidence >= min_confidence else "keep_in_short_term",
        }

    return None


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    fixtures_path = os.path.join(script_dir, "fixtures", "reflection_input.json")
    with open(fixtures_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    memories = data["recent_memories"]
    config = data["reflection_config"]

    print("=" * 85)
    print("X1-12 Reflection 蒸馏")
    print(f"输入: {len(memories)} 条近期记忆")
    print(f"Reflection 配置: 最少关联数={config['min_related_count']}, "
          f"时间窗口={config['time_window_days']}天, 最小置信度={config['min_confidence']}")
    print(f"{'=' * 85}")

    # Step 1: 按话题分组
    groups = group_by_topic(memories)
    print(f"\n步骤 1：按话题分组")
    for topic, mems in groups.items():
        print(f"  [{topic}] {len(mems)} 条记忆")
        for m in mems:
            print(f"    - [{m['id']}] {m['content'][:60]}...")

    # Step 2: 对每组执行 reflection
    print(f"\n步骤 2：Reflection 分析")
    consolidated = []
    for topic, mems in groups.items():
        result = reflection_analyze(
            topic, mems,
            min_count=config["min_related_count"],
            min_confidence=config["min_confidence"],
        )
        if result:
            status = "[v] 蒸馏为长期事实" if result["action"] == "consolidate_to_long_term" else "○ 保留在中期层"
            print(f"\n  [{topic}] → {status}")
            print(f"    蒸馏结果: {result['distilled_fact']}")
            print(f"    置信度: {result['confidence']:.2f}")
            print(f"    支撑证据: {result['supporting_count']} 条记忆 ({', '.join(result['source_memories'])})")
            if result["confidence"] >= config["min_confidence"]:
                consolidated.append(result)
        else:
            print(f"\n  [{topic}] → 跳过（只有 {len(mems)} 条记忆，不足 {config['min_related_count']} 条）")

    # Step 3: 展示蒸馏效果
    print(f"\n{'-' * 85}")
    print("步骤 3：蒸馏前后对比")
    print(f"{'-' * 85}")
    total_original = len(memories)
    total_distilled = len(consolidated)
    print(f"  原始记忆: {total_original} 条")
    print(f"  蒸馏后稳定事实: {total_distilled} 条")
    print(f"  压缩比: {total_original}:{total_distilled} "
          f"({total_original/total_distilled:.1f}:1)" if total_distilled > 0 else "")

    if consolidated:
        print(f"\n  进入长期层的事实：")
        for c in consolidated:
            print(f"    * [{c['topic']}] {c['distilled_fact']} (置信度={c['confidence']:.2f})")

    print(f"\n  关键观察：")
    print(f"    1. Reflection 是「从多条记忆中发现模式」的过程")
    print(f"    2. 不是所有话题都有足够的证据形成稳定事实")
    print(f"    3. 置信度门槛（如 0.7）决定了哪些进入长期层")
    print(f"    4. 蒸馏后的事实比原始记忆更抽象、更稳定、衰减更慢")
    print(f"    5. 实际系统中 Reflection 通过 LLM 完成，规则模拟仅作演示")
    print()


if __name__ == "__main__":
    main()
