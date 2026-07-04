"""
x1_13_profile_vs_facts.py — 画像 + 事实库组合检索

本脚本演示论文中关键的架构决策: 为什么要把"用户画像"和"向量事实库"分开存储?

对比三种检索方式:
  A. 仅画像 (精确读取): 快、准，但覆盖不到画像字段之外的长尾信息
  B. 仅事实库 (语义搜索): 广、长尾，但确定性信息可能被语义模糊匹配漏掉
  C. 组合检索: 画像提供确定性约束 + 事实库提供上下文补充 → 最完整

运行:
  python x1_13_profile_vs_facts.py

输入: fixtures/user_profile.json (结构化画像 + 向量事实列表)
输出:
  - 4 个不同查询下三种方式的返回结果对比
  - 组合检索的设计原则总结

对应正文: X1-3 §3 "画像与事实库为什么要分开"
"""

import json
import os
from typing import Any


def load_profile(filepath: str) -> dict:
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def query_profile_only(profile: dict, query: str) -> dict:
    """仅从画像中查询，返回匹配的字段"""
    flat_profile = {}

    def flatten(d, prefix=""):
        for k, v in d.items():
            key = f"{prefix}.{k}" if prefix else k
            if isinstance(v, dict):
                flatten(v, key)
            elif isinstance(v, list):
                flat_profile[key] = ", ".join(str(x) for x in v)
            else:
                flat_profile[key] = str(v)

    flatten(profile["profile"])

    # 用主题关键词字典识别 query 涉及的话题（中文友好）
    query_keywords = _extract_query_keywords(query)

    results = {}
    for key, value in flat_profile.items():
        # 任一查询关键词出现在 key 或 value 中即视为命中
        if any(kw in key.lower() or kw in value.lower() for kw in query_keywords):
            results[key] = value
    return results


def _extract_query_keywords(query: str) -> list[str]:
    """
    从 query 中提取相关关键词。
    返回的 keywords 既包含中文话题词，也包含对应的英文桥接词（用来匹配 profile 的英文 key）。
    例如 query 含"编程语言" → 返回 ['编程', '语言', 'language', 'Python', 'Java', 'Go', 'Rust']
    """
    # 主题词典：每条 topic 包含 (a) 中文/英文触发词（用来判断 query 是否涉及该主题）
    #         (b) 桥接词（一旦确定涉及，就把这些都当成 query 关键词）
    topic_keywords = {
        "编程语言": {
            "triggers": ["编程", "语言", "开发", "后端", "主力", "框架", "Python", "Java", "Go", "Rust"],
            "bridges": ["编程", "语言", "开发", "后端", "主力", "框架",
                        "language", "framework", "Python", "Java", "Go", "Rust"],
        },
        "食物偏好": {
            "triggers": ["吃", "披萨", "素", "食物", "饮食", "餐厅", "过敏", "花生", "肉类"],
            "bridges": ["吃", "披萨", "素", "食物", "饮食", "餐厅", "过敏", "花生", "肉类",
                        "dietary", "allergies", "food"],
        },
        "云平台": {
            "triggers": ["AWS", "阿里云", "云平台", "云服务", "云", "迁移"],
            "bridges": ["AWS", "阿里云", "云平台", "云服务", "云", "迁移", "cloud"],
        },
        "编辑器": {
            "triggers": ["VS Code", "编辑器", "IDE", "插件"],
            "bridges": ["VS Code", "编辑器", "IDE", "插件", "editor"],
        },
        "电商项目": {
            "triggers": ["电商", "项目", "Django", "PostgreSQL", "技术栈"],
            "bridges": ["电商", "项目", "Django", "PostgreSQL", "技术栈", "project"],
        },
        "代码风格": {
            "triggers": ["代码", "风格", "注释", "简洁"],
            "bridges": ["代码", "风格", "注释", "简洁", "code_style"],
        },
        "健康": {
            "triggers": ["健康", "过敏", "花生", "注意事项", "饮食"],
            "bridges": ["健康", "过敏", "花生", "注意事项", "饮食",
                        "health", "allergies", "dietary"],
        },
        "技术方案": {
            "triggers": ["技术", "方案", "推荐", "适合", "微服务"],
            "bridges": ["技术", "方案", "推荐", "适合", "微服务", "后端"],
        },
        "学习": {
            "triggers": ["学", "教程", "初学者", "考虑", "学习"],
            "bridges": ["学", "教程", "初学者", "考虑", "学习", "learning"],
        },
    }

    matched_topics = [
        topic for topic, mapping in topic_keywords.items()
        if any(tr in query for tr in mapping["triggers"])
    ]

    keywords = []
    for topic in matched_topics:
        keywords.extend(topic_keywords[topic]["bridges"])

    # fallback：如果主题词典没匹配上，按字符级 fallback 取 ≥2 字符的中文片段
    if not keywords:
        import re
        cn_chunks = re.findall(r'[一-鿿]{2,}', query)
        keywords.extend(cn_chunks)

    return keywords


def query_facts_only(facts: list, query: str) -> list:
    """仅从事实库语义搜索（模拟）"""
    query_keywords = _extract_query_keywords(query)

    results = []
    for fact in facts:
        content = fact["content"]
        if not query_keywords:
            continue
        hits = sum(1 for kw in query_keywords if kw in content)
        if hits == 0:
            continue
        score = hits / max(len(query_keywords), 1)
        results.append({"content": fact["content"], "score": score, "category": fact["category"]})
    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:5]


def query_combined(profile: dict, facts: list, query: str) -> dict:
    """组合检索：先画像，后事实库"""
    profile_results = query_profile_only(profile, query)
    fact_results = query_facts_only(facts, query)
    return {
        "deterministic": profile_results,  # 确定性约束
        "contextual": fact_results,         # 上下文补充
    }


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    fixtures_path = os.path.join(script_dir, "fixtures", "user_profile.json")
    profile_data = load_profile(fixtures_path)

    queries = [
        "用户用什么编程语言",
        "推荐一个适合用户的后端技术方案",
        "用户有什么健康注意事项",
        "用户最近在忙什么项目",
    ]

    print("=" * 85)
    print("X1-13 画像 + 事实库组合检索")
    print(f"{'=' * 85}")

    for query in queries:
        print(f"\n{'-' * 85}")
        print(f"查询: 「{query}」")
        print(f"{'-' * 85}")

        # 方式 1：仅画像
        profile_only = query_profile_only(profile_data, query)
        print(f"\n  【方式 A：仅画像】返回 {len(profile_only)} 个字段")
        if profile_only:
            for k, v in profile_only.items():
                print(f"    {k}: {v}")
        else:
            print(f"    (无匹配 → 纯画像查询信息不足)")

        # 方式 2：仅事实库
        facts_only = query_facts_only(profile_data["vector_facts"], query)
        print(f"\n  【方式 B：仅事实库】返回 {len(facts_only)} 条")
        for f in facts_only:
            print(f"    [{f['category']}] (相关度={f['score']:.2f}) {f['content']}")

        # 方式 3：组合
        combined = query_combined(profile_data, profile_data["vector_facts"], query)
        print(f"\n  【方式 C：组合检索】")
        print(f"    确定性约束（画像）: {len(combined['deterministic'])} 个字段")
        for k, v in combined["deterministic"].items():
            print(f"      {k}: {v}")
        print(f"    上下文补充（事实库）: {len(combined['contextual'])} 条")
        for f in combined["contextual"]:
            print(f"      [{f['category']}] {f['content']}")

        # 分析
        print(f"\n  分析：")
        if not profile_only and facts_only:
            print(f"    → 画像无匹配，但事实库有 {len(facts_only)} 条相关。")
            print(f"    → 纯画像查询会漏掉这些长尾信息。")
        elif profile_only and not facts_only:
            print(f"    → 画像能提供确定性答案，事实库无额外补充。")
            print(f"    → 仅画像就够，不需要消耗事实库检索的 Token。")
        elif profile_only and facts_only:
            print(f"    → 画像提供确定性约束，事实库提供上下文细节。")
            print(f"    → 组合效果 > 各自单独使用。")

    # 总结
    print(f"\n{'=' * 85}")
    print("组合检索的设计原则")
    print(f"{'=' * 85}")
    print(f"  1. 画像优先：确定性信息从画像中按 key 直接读取，不经过语义匹配")
    print(f"     → 避免 '用户是 Go 开发者' 因语义模糊被漏掉")
    print(f"  2. 事实库补充：长尾信息、情景记忆通过语义搜索从事实库获取")
    print(f"     → 覆盖画像字段以外的丰富上下文")
    print(f"  3. 最终 Prompt = 画像字段(确定性) + 事实库 Top-N(补充)")
    print(f"     → 确定性信息确保准确，语义补充确保全面")
    print()


if __name__ == "__main__":
    main()
