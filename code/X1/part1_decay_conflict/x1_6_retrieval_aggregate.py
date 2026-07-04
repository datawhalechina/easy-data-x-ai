"""
x1_6_retrieval_aggregate.py — 确定性聚合 vs 全量上下文

当多条矛盾记忆同时被检索到, 有两种处理策略:
  A. 确定性聚合: 代码层先合并（取最新 active 版本、过滤已失效的），结果一致可复现
  B. 全量上下文: 所有候选记忆都塞进 Prompt 给 LLM 判断，灵活但不稳定

运行:
  python x1_6_retrieval_aggregate.py

输出:
  - 同一 query 下两种策略的返回结果对比
  - 确定性聚合节省的 Token 估算
  - 策略选择建议: 简单事实→确定性, 复杂偏好→全量上下文

对应正文: X1-1 §4.3 "确定性聚合：检索之后、进 Prompt 之前"
"""

import json
import os


def load_data(filepath: str) -> dict:
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def deterministic_aggregate(candidates: list, query: str) -> dict:
    """
    确定性聚合策略：
    - 同一话题只返回最新 active 版本
    - 多个话题分别返回各自的 active 版本
    - 并存偏好全部返回但标注
    """
    # 按话题分组（简化：用关键词重叠判断话题）
    topics = _group_by_topic(candidates)

    aggregated = []
    discarded = []

    for topic_key, group in topics.items():
        active_mems = [m for m in group if m.get("is_active", True)]
        inactive_mems = [m for m in group if not m.get("is_active", True)]

        if len(active_mems) == 1:
            # 单个 active → 直接返回
            aggregated.append(active_mems[0])
            for im in inactive_mems:
                discarded.append({
                    "id": im["id"],
                    "content": im["content"],
                    "reason": f"已被 {active_mems[0]['id']} 取代",
                })
        elif len(active_mems) > 1:
            # 多个 active → 并存偏好，全部保留
            for am in active_mems:
                aggregated.append(am)
        elif inactive_mems:
            # 只有 inactives → 返回最新的
            latest = max(inactive_mems, key=lambda m: m.get("created_at", ""))
            aggregated.append(latest)

    return {
        "strategy": "deterministic",
        "results": aggregated,
        "discarded": discarded,
        "result_count": len(aggregated),
    }


def _group_by_topic(memories: list) -> dict:
    """按话题分组（简化实现：用关键词重叠）"""
    groups = {}
    for mem in memories:
        content = mem["content"]
        # 提取主题词
        topics_keywords = {
            "编程语言": ["编程语言", "Java", "Go", "Python", "Rust", "开发"],
            "食物偏好": ["吃", "披萨", "素", "食物", "饮食"],
            "云平台": ["AWS", "阿里云", "云平台", "迁移"],
            "编辑器": ["编辑器", "VS Code", "IDE"],
            "电商项目": ["电商", "项目", "Django", "PostgreSQL"],
        }

        matched = "其他"
        for topic, keywords in topics_keywords.items():
            if any(kw in content for kw in keywords):
                matched = topic
                break

        if matched not in groups:
            groups[matched] = []
        groups[matched].append(mem)

    return groups


def full_context_approach(candidates: list, query: str) -> dict:
    """
    全量上下文策略（模拟）：
    把所有候选记忆都返回，估计 Token 消耗
    """
    total_chars = sum(len(c["content"]) for c in candidates)
    estimated_tokens = total_chars * 0.5  # 粗略：中文约 2 字/token

    return {
        "strategy": "full_context",
        "results": candidates,
        "result_count": len(candidates),
        "estimated_tokens": int(estimated_tokens),
        "estimated_prompt_tokens": int(estimated_tokens + 200),  # 含 query 和指令
    }


def simulate_semantic_score(content: str, query: str) -> float:
    """
    模拟语义相似度分数（中文友好）。
    实际系统中这是 embedding 余弦相似度，这里用主题关键词字典模拟。
    """
    topic_keywords = {
        "编程语言": ["Python", "Java", "Go", "Rust", "编程", "语言", "开发", "后端", "主力", "框架"],
        "食物偏好": ["吃", "披萨", "素", "食物", "饮食", "餐厅", "过敏", "花生", "肉类"],
        "云平台": ["AWS", "阿里云", "云平台", "云服务", "云", "迁移"],
        "编辑器": ["VS Code", "编辑器", "IDE", "插件"],
        "电商项目": ["电商", "项目", "Django", "PostgreSQL", "技术栈"],
        "代码风格": ["代码", "风格", "注释", "简洁"],
        "学习": ["学", "教程", "初学者", "考虑"],
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


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    fixtures_path = os.path.join(script_dir, "fixtures", "sample_memories.json")
    data = load_data(fixtures_path)

    print("=" * 85)
    print("X1-6 检索结果聚合：确定性聚合 vs 全量上下文")
    print(f"{'=' * 85}")

    for q in data["queries"]:
        print(f"\n{'-' * 85}")
        print(f"查询: 「{q['query_text']}」")
        print(f"{'-' * 85}")

        # 模拟搜索：用主题关键词匹配圈定候选集
        candidates = []
        for mem in data["memories"]:
            score = simulate_semantic_score(mem["content"], q["query_text"])
            if score > 0:
                candidates.append({**mem, "_sem_score": score})

        # 策略 1：确定性聚合
        det_result = deterministic_aggregate(candidates, q["query_text"])

        # 策略 2：全量上下文
        ctx_result = full_context_approach(candidates, q["query_text"])

        print(f"\n  【策略 A：确定性聚合】返回 {det_result['result_count']} 条")
        for r in det_result["results"]:
            active_tag = "[v]" if r.get("is_active", True) else "[x]"
            print(f"    [{r['id']}] (active={active_tag}) {r['content']}")
        if det_result["discarded"]:
            print(f"  已过滤 {len(det_result['discarded'])} 条：")
            for d in det_result["discarded"]:
                print(f"    [x] [{d['id']}] {d['content'][:50]} — {d['reason']}")

        print(f"\n  【策略 B：全量上下文】返回 {ctx_result['result_count']} 条")
        for r in ctx_result["results"]:
            print(f"    [{r['id']}] {r['content'][:60]}")
        print(f"  估计 Token 消耗: ~{ctx_result['estimated_tokens']} tokens（仅记忆内容）")
        print(f"  含 Prompt 指令: ~{ctx_result['estimated_prompt_tokens']} tokens")

        # 对比
        det_chars = sum(len(r["content"]) for r in det_result["results"])
        det_tokens = int(det_chars * 0.5)
        token_diff = ctx_result["estimated_tokens"] - det_tokens
        print(f"\n  对比：确定性聚合节省约 {max(0, token_diff)} tokens，且结果一致可复现")

        # 检查是否符合预期
        if "expected_answer_deterministic" in q:
            print(f"  预期（确定性）: {q['expected_answer_deterministic']}")
        if "expected_answer_context" in q:
            print(f"  预期（上下文）: {q['expected_answer_context']}")
        if "note" in q:
            print(f"  注: {q['note']}")

    # 总结
    print(f"\n{'=' * 85}")
    print("策略选择建议")
    print(f"{'=' * 85}")
    print(f"  确定性聚合适用场景：")
    print(f"    - 简单事实查询（'用户用什么语言？'）")
    print(f"    - 答案唯一、不需要 LLM 综合推理")
    print(f"    - 对一致性要求高（同一问题两次返回必须相同）")
    print(f"  全量上下文适用场景：")
    print(f"    - 复杂偏好综合判断（'用户会喜欢这个方案吗？'）")
    print(f"    - 需要 LLM 理解并存矛盾的上下文")
    print(f"    - Token 预算充足、对一致性要求不高")
    print()


if __name__ == "__main__":
    main()
