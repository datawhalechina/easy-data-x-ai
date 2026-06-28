#!/usr/bin/env python3
"""
X2 示例：对比 Skill 全量注入 vs 按需加载的上下文开销。

运行前请先执行：
    python database/init_seekdb.py
    python tools/migrate.py skills/ --all
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from services import QueryService, SkillService
from database.collections import DEFAULT_SEEKDB_PATH

DB_PATH = str(Path(__file__).parent / DEFAULT_SEEKDB_PATH)


def estimate_tokens(text: str) -> int:
    return len(text) // 3


def full_injection_context() -> tuple[str, int]:
    service = SkillService(DB_PATH)
    skills = service.list_skills()
    parts = []
    for skill in skills:
        parts.append(f"## Skill: {skill.name}\n{skill.description}\n\n{skill.content}")
    context = "\n\n---\n\n".join(parts)
    return context, estimate_tokens(context)


def on_demand_context(user_query: str) -> tuple[str, int]:
    query_service = QueryService(DB_PATH)
    matched = query_service.search_skills(user_query, n_results=2)
    if not matched:
        matched = query_service.search_skills("documentation", n_results=1)

    parts = []
    for skill in matched:
        rules = query_service.get_rules_by_skill(skill.name)
        top_rules = sorted(rules, key=lambda r: r.priority, reverse=True)[:5]
        rule_text = "\n".join(f"- {r.rule_value}" for r in top_rules)
        parts.append(
            f"## Skill: {skill.name}\n{skill.description}\n\n"
            f"### Key Rules\n{rule_text}"
        )
    context = "\n\n---\n\n".join(parts)
    return context, estimate_tokens(context)


def main():
    user_query = "帮我写一份 REST API 接口文档"

    print("=" * 60)
    print("X2 · Skill 上下文开销对比 (seekdb)")
    print("=" * 60)
    print(f"\n用户请求: {user_query}\n")

    full_ctx, full_tokens = full_injection_context()
    on_demand_ctx, on_demand_tokens = on_demand_context(user_query)

    print("【方式一】全量注入")
    print(f"  加载 Skill 数: {len(SkillService(DB_PATH).list_skills())}")
    print(f"  上下文字符数: {len(full_ctx):,}")
    print(f"  估算 Token 数: ~{full_tokens:,}")

    print("\n【方式二】按需加载 (seekdb hybrid search)")
    print(f"  上下文字符数: {len(on_demand_ctx):,}")
    print(f"  估算 Token 数: ~{on_demand_tokens:,}")

    if full_tokens > 0:
        saved = (1 - on_demand_tokens / full_tokens) * 100
        print(f"\n  节省上下文: ~{saved:.0f}%")

    print("\n按需加载上下文预览（前 500 字符）:")
    print("-" * 40)
    print(on_demand_ctx[:500])
    if len(on_demand_ctx) > 500:
        print("...")


if __name__ == "__main__":
    main()
