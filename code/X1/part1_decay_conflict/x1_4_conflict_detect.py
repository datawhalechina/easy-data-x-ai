"""
x1_4_conflict_detect.py — 冲突检测与路由 (ADD/UPDATE/DELETE/NONE)

本脚本回答: 新事实写入时，怎么自动发现它和已有记忆是矛盾还是补充？

两步流程:
  1. 向量相似度粗筛: 新事实 embedding × 存量记忆 embedding → 余弦相似度 > threshold
  2. 规则路由: 根据相似度高低 + 关键词特征，决定四个动作之一

运行:
  python x1_4_conflict_detect.py

输出:
  - 每条新事实 vs 存量记忆的相似度排名
  - 路由决策 (ADD/UPDATE/DELETE/NONE) 及原因
  - 阈值取舍分析（太高漏检 / 太低误报）

关键参数:
  similarity_threshold = 0.3: 进入候选集的最低相似度；0.25~0.35 推荐起步
  实际系统中步骤 2 由 LLM 完成 (PowerMem 的 _decide_memory_actions)，规则版仅演示逻辑

对应正文: X1-1 §4.1 "从相似度到路由决策"
"""

import json
import os
from typing import Literal

ActionType = Literal["ADD", "UPDATE", "DELETE", "NONE"]


def simulate_similarity(text_a: str, text_b: str) -> float:
    """
    模拟 embedding 余弦相似度（中文友好）。
    实际系统中使用 embedding 模型计算，这里用「主题关键词重叠 + 字符级 Jaccard」模拟。
    """
    if not text_a or not text_b:
        return 0.0

    # 主题词典：覆盖示例库涉及的话题
    topic_keywords = {
        "编程语言": ["Python", "Java", "Go", "Rust", "编程", "语言", "开发", "后端", "主力", "框架", "微服务"],
        "食物偏好": ["吃", "披萨", "素", "食物", "饮食", "餐厅", "过敏", "花生", "肉类"],
        "云平台": ["AWS", "阿里云", "云平台", "云服务", "云", "迁移"],
        "编辑器": ["VS Code", "编辑器", "IDE", "插件"],
        "电商项目": ["电商", "项目", "Django", "PostgreSQL", "技术栈", "跨境", "支付"],
        "代码风格": ["代码", "风格", "注释", "简洁"],
        "学习": ["学", "教程", "初学者", "考虑", "学习"],
    }

    # 找出两条文本各自涉及的话题
    topics_a = {t for t, kws in topic_keywords.items() if any(kw in text_a for kw in kws)}
    topics_b = {t for t, kws in topic_keywords.items() if any(kw in text_b for kw in kws)}

    # 字符级 Jaccard 作为基础分（保证同语言文本之间有非零相似度）
    chars_a = set(text_a)
    chars_b = set(text_b)
    char_jaccard = len(chars_a & chars_b) / max(len(chars_a | chars_b), 1)

    if not topics_a or not topics_b:
        # 无主题识别，只用字符级
        return min(1.0, char_jaccard * 1.5)

    # 话题重叠度
    topic_overlap = len(topics_a & topics_b) / max(len(topics_a | topics_b), 1)

    # 在重叠话题下，统计共享的关键词数
    keyword_overlap = 0
    for topic in topics_a & topics_b:
        kw_a = {kw for kw in topic_keywords[topic] if kw in text_a}
        kw_b = {kw for kw in topic_keywords[topic] if kw in text_b}
        keyword_overlap += len(kw_a & kw_b)

    # 综合：话题重叠为主，关键词共享做加分，字符级做兜底
    score = topic_overlap * 0.6 + keyword_overlap * 0.15 + char_jaccard * 0.15
    return min(1.0, score)


def detect_conflict(new_fact: str, existing_memories: list, similarity_threshold: float = 0.3) -> dict:
    """
    冲突检测主流程：
    1. 向量相似度粗筛，取 ≥ threshold 的候选
    2. 规则路由：判断动作类型
    """
    candidates = []
    for mem in existing_memories:
        sim = simulate_similarity(new_fact, mem["content"])
        if sim >= similarity_threshold and mem["is_active"]:
            candidates.append({**mem, "similarity": sim})

    candidates.sort(key=lambda x: x["similarity"], reverse=True)

    if not candidates:
        return {"action": "ADD", "reason": "无相似已有记忆，新增", "candidates": []}

    top = candidates[0]

    # 规则路由（简化版；实际系统中由 LLM 判断）
    # 1. 高度相似 + 关键词重叠很高 → 可能是冲突/更新
    # 2. 中等相似 → 可能是补充/并存
    # 3. 低相似但过阈值 → 可能是相关但独立

    if top["similarity"] >= 0.7:
        # 高相似度：优先判断是否为「时间演进/迁移」类（如 Java→Go、AWS→阿里云）
        # 这类语句明确指出旧事实已被取代，应走 UPDATE 而非 DELETE
        transition_keywords = ["已从", "转向", "迁移", "改为", "全面", "切换到", "换成", "替代"]
        is_transition = any(kw in new_fact for kw in transition_keywords)

        # 否定词仅保留真正的「直接否定」语义，不再包含「已从/转向/改为」
        # （后者是时间演进，不是逻辑否定）
        negative_keywords = ["不", "不是", "没有", "不再", "讨厌", "不喜欢", "从不", "绝不"]
        has_negation = any(kw in new_fact for kw in negative_keywords)

        # 路由优先级：迁移 > 否定 > 细化
        # 原因：迁移语句通常同时包含「转向」和「不」（如"已从 Java 转向 Go，不再用 Java"），
        # 但语义上属于 UPDATE（保留 Java 作为历史版本），而非 DELETE
        if is_transition:
            return {
                "action": "UPDATE",
                "reason": f"时间演进/技术迁移：新事实替代已有记忆（相似度={top['similarity']:.2f}）",
                "target_id": top["id"],
                "candidates": candidates,
            }

        if has_negation and top["similarity"] >= 0.85:
            return {
                "action": "DELETE",
                "reason": f"直接矛盾：新事实否定已有记忆（相似度={top['similarity']:.2f}）",
                "target_id": top["id"],
                "candidates": candidates,
            }

        return {
            "action": "UPDATE",
            "reason": f"细化/更新：新事实对已有记忆的补充（相似度={top['similarity']:.2f}）",
            "target_id": top["id"],
            "candidates": candidates,
        }
    elif top["similarity"] >= 0.5:
        return {
            "action": "ADD",
            "reason": f"并存偏好：相关但不矛盾，并行保留（相似度={top['similarity']:.2f}）",
            "candidates": candidates,
        }
    else:
        return {
            "action": "ADD",
            "reason": f"弱相关：独立信息，新增（相似度={top['similarity']:.2f}）",
            "candidates": candidates,
        }


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    fixtures_path = os.path.join(script_dir, "fixtures", "sample_memories.json")
    with open(fixtures_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    memories = data["memories"]

    # 测试用例：新事实 vs 已有记忆（覆盖四种路由：UPDATE / ADD / DELETE / 细化）
    test_facts = [
        # UPDATE（时间演进）：含「已从...转向」迁移词
        "用户已从 Java 全面转向 Go 语言开发",
        # ADD（并存偏好）：同主题但不矛盾，不构成否定
        "用户喜欢尝试各种意大利菜，尤其偏爱意面",
        # DELETE（直接矛盾）：含「讨厌」否定词，与 mem_007 直接对立
        "用户非常讨厌披萨，从来不吃",
        # UPDATE（细化补充）：补充 mem_006 的项目细节
        "用户的电商项目涉及跨境支付和多币种结算",
        # ADD（弱相关）：独立新信息
        "用户正在考虑学习 Kubernetes",
    ]

    print("=" * 85)
    print("X1-4 冲突检测与路由")
    print(f"相似度阈值: 0.3（低于此值不进入候选）")
    print(f"高冲突阈值: 0.7（高于此值触发 UPDATE/DELETE）")
    print(f"{'=' * 85}")

    for fact in test_facts:
        print(f"\n{'-' * 85}")
        print(f"新事实: 「{fact}」")
        print(f"{'-' * 85}")

        result = detect_conflict(fact, memories)

        # 候选记忆
        if result["candidates"]:
            print(f"\n  候选已有记忆 ({len(result['candidates'])} 条)：")
            for c in result["candidates"][:3]:
                print(f"    [{c['id']}] (相似度={c['similarity']:.2f}) {c['content'][:60]}")

        print(f"\n  路由决策: {result['action']}")
        print(f"  原因: {result['reason']}")
        if "target_id" in result:
            target = next(m for m in memories if m["id"] == result["target_id"])
            print(f"  操作对象: [{result['target_id']}] {target['content'][:60]}")

    # 展示冲突检测的漏检/误报边界
    print(f"\n{'=' * 85}")
    print("阈值取舍分析")
    print(f"{'=' * 85}")
    print(f"  当前阈值: 0.3")
    print(f"  如果阈值设太高（如 0.6）：")
    print(f"    → 「用户考虑学 K8s」和「用户正在学 Rust」相似度约 0.3")
    print(f"    → 阈值 0.6 时不会进入候选，但实际应该提醒「用户同时学两门新技术」")
    print(f"  如果阈值设太低（如 0.1）：")
    print(f"    → 大量不相关记忆进入候选，LLM 调用成本飙升")
    print(f"    → 需要 LLM 精确判断，但成本与延迟不可接受")
    print(f"  实践建议：0.25-0.35 起步，根据误报率和漏检率微调")
    print()


if __name__ == "__main__":
    main()
