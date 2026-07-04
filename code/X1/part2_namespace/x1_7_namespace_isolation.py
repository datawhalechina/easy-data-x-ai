"""
x1_7_namespace_isolation.py — 命名空间隔离验证

本脚本验证多 Agent 记忆最基础的安全属性: 默认相互不可见。

模拟 PowerMem 的三级隔离键:
  user_id: 用户维度的隔离（一级）
  agent_id: Agent 维度的隔离（二级）
  run_id:   会话维度的隔离（三级）

运行:
  python x1_7_namespace_isolation.py

实验设计:
  - Agent A (代码助手) 写入 3 条技术相关记忆
  - Agent B (生活助手) 写入 2 条生活相关记忆
  - 验证 Agent A 搜索"饮食 过敏"时，看不到 Agent B 的记忆

关键设计决策: 查询构建阶段就注入过滤条件
  这是 PowerMem _build_db_filters 的设计哲学——过滤发生在数据库索引层，
  而不是在应用代码中过滤全量搜索结果。

对应正文: X1-2 §1.1 "命名空间：三个字段决定谁能看到什么"
"""

import json
import os
from datetime import datetime
from typing import Any


class NamespaceMemoryStore:
    """
    模拟带命名空间隔离的记忆存储。
    实际 PowerMem 中这通过 _SYSTEM_FILTER_KEYS 在 SQL WHERE 子句中实现。
    """

    def __init__(self):
        self._store: list[dict[str, Any]] = []

    def add(
        self,
        content: str,
        user_id: str,
        agent_id: str,
        run_id: str = "default",
        scope: str = "PRIVATE",
        importance: float = 0.5,
    ) -> str:
        """写入记忆，带完整的命名空间标记"""
        mem_id = f"mem_{len(self._store) + 1:03d}"
        memory = {
            "id": mem_id,
            "content": content,
            "user_id": user_id,
            "agent_id": agent_id,
            "run_id": run_id,
            "scope": scope,
            "importance_score": importance,
            "created_at": datetime.now().isoformat(),
            "is_active": True,
        }
        self._store.append(memory)
        return mem_id

    def search(
        self,
        query: str,
        user_id: str,
        agent_id: str,
        scope_filter: list[str] | None = None,
    ) -> list:
        """
        检索记忆。关键：user_id + agent_id 在查询构建阶段就注入过滤条件。
        这与 PowerMem 的 _build_db_filters 设计一致。
        """
        results = []
        query_lower = query.lower()

        for mem in self._store:
            # 命名空间隔离：只返回当前 agent 的记忆
            if mem["user_id"] != user_id:
                continue
            if mem["agent_id"] != agent_id:
                continue
            if scope_filter and mem["scope"] not in scope_filter:
                continue
            if not mem["is_active"]:
                continue

            # 简单的关键词匹配模拟语义搜索
            content_lower = mem["content"].lower()
            keywords = query_lower.split()
            relevance = sum(1 for kw in keywords if kw in content_lower) / max(len(keywords), 1)

            if relevance > 0:
                results.append({**mem, "relevance": relevance})

        results.sort(key=lambda x: x["relevance"], reverse=True)
        return results

    def get_all_for_user(self, user_id: str) -> list:
        """获取某用户的所有记忆（仅用于调试对比）"""
        return [m for m in self._store if m["user_id"] == user_id]


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    fixtures_path = os.path.join(script_dir, "fixtures", "agents.json")
    with open(fixtures_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    user_id = config["user_id"]
    store = NamespaceMemoryStore()

    print("=" * 85)
    print("X1-7 命名空间隔离验证")
    print(f"用户: {user_id}")
    print(f"{'=' * 85}")

    # Agent A (代码助手) 写入记忆
    agent_a = config["agents"][0]  # agent_code_assistant
    store.add("用户正在用 Go 开发微服务，需要 gRPC 相关的帮助",
              user_id, agent_a["agent_id"])
    store.add("用户偏好使用 VS Code，已配置 Go 开发环境",
              user_id, agent_a["agent_id"])
    store.add("用户的代码风格偏好：简洁、不喜欢过多注释",
              user_id, agent_a["agent_id"])
    print(f"\n  {agent_a['name']} ({agent_a['agent_id']}) 写入了 3 条记忆")

    # Agent B (生活助手) 写入记忆
    agent_b = config["agents"][1]  # agent_life_assistant
    store.add("用户对花生过敏，所有饮食建议必须避开",
              user_id, agent_b["agent_id"])
    store.add("用户最近在尝试素食，推荐素食餐厅",
              user_id, agent_b["agent_id"])
    print(f"  {agent_b['name']} ({agent_b['agent_id']}) 写入了 2 条记忆")

    # 验证隔离
    print(f"\n{'-' * 85}")
    print("隔离验证：Agent A 检索自己的记忆")
    print(f"{'-' * 85}")
    results_a = store.search("开发 编程", user_id, agent_a["agent_id"])
    for r in results_a:
        print(f"  [{r['id']}] (scope={r['scope']}) {r['content']}")
    print(f"  共 {len(results_a)} 条 → Agent A 只能看到自己的记忆")

    print(f"\n{'-' * 85}")
    print("隔离验证：Agent B 检索自己的记忆")
    print(f"{'-' * 85}")
    results_b = store.search("饮食 健康", user_id, agent_b["agent_id"])
    for r in results_b:
        print(f"  [{r['id']}] (scope={r['scope']}) {r['content']}")
    print(f"  共 {len(results_b)} 条 → Agent B 只能看到自己的记忆")

    # 交叉验证：Agent A 尝试查看 Agent B 的记忆
    print(f"\n{'-' * 85}")
    print("交叉验证：Agent A 搜索「饮食 过敏」（Agent B 的记忆领域）")
    print(f"{'-' * 85}")
    cross_results = store.search("饮食 过敏 素食", user_id, agent_a["agent_id"])
    if not cross_results:
        print(f"  (无结果) → 正确！Agent A 看不到 Agent B 的记忆")
    else:
        print(f"  [!] 泄漏！Agent A 看到了 {len(cross_results)} 条不属于它的记忆")

    # 全量视图（调试用）
    print(f"\n{'-' * 85}")
    print("全量记忆清单（仅用于调试对比，生产环境不会有此接口）")
    print(f"{'-' * 85}")
    all_mems = store.get_all_for_user(user_id)
    print(f"  {'Agent':<25} {'Scope':<10} {'内容':<45}")
    print(f"  {'-' * 80}")
    for m in all_mems:
        print(f"  {m['agent_id']:<25} {m['scope']:<10} {m['content'][:42]}")

    print(f"\n  关键观察：同一个 user_id 下有 5 条记忆，")
    print(f"  但每个 Agent 只能检索到属于自己的那部分。")
    print(f"  agent_id 作为检索过滤条件，在查询构建阶段就已注入。")
    print()


if __name__ == "__main__":
    main()
