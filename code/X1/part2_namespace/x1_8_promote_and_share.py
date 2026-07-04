"""
x1_8_promote_and_share.py — 权限提升与跨 Agent 共享

本脚本演示: 如何安全地将一条 PRIVATE 记忆 promote 到 AGENT_GROUP, 让同组其他 Agent 可见。

PowerMem 的 scope 层级设计 (只能向更开放的方向 promote):
  PRIVATE(0)  ──promote──>  AGENT_GROUP(1)  ──promote──>  PUBLIC(2)

运行:
  python x1_8_promote_and_share.py

实验设计:
  - 代码助手(dev_tools 组) 写入技术偏好 → PRIVATE
  - 验证 PM 助手(dev_tools 组) 看不到
  - promote 到 AGENT_GROUP(dev_tools) → PM 助手现在可检索
  - 验证生活助手(life_tools 组) 仍然看不到 dev_tools 组的记忆
  - 审计日志: 所有 promote 操作都有时间+操作者记录

对应正文: X1-2 §2.2 "Promote：只能向更开放的方向移动"
"""

import json
import os
from datetime import datetime
from typing import Any


SCOPE_LEVEL = {"PRIVATE": 0, "AGENT_GROUP": 1, "USER_GROUP": 2, "PUBLIC": 3}


class MemoryWithScope:
    """带作用域管理和 ACL 的记忆存储"""

    def __init__(self, agents_config: dict):
        self._store: list[dict[str, Any]] = []
        self._agents = agents_config["agents"]
        self._groups = agents_config["agent_groups"]
        self._audit_log: list[dict] = []

    def add(self, content: str, user_id: str, agent_id: str, scope: str = "PRIVATE") -> str:
        mem_id = f"mem_{len(self._store) + 1:03d}"
        self._store.append({
            "id": mem_id,
            "content": content,
            "user_id": user_id,
            "agent_id": agent_id,
            "scope": scope,
            "created_at": datetime.now().isoformat(),
            "is_active": True,
            "scope_history": [{"scope": scope, "changed_at": datetime.now().isoformat()}],
        })
        return mem_id

    def promote(
        self,
        memory_id: str,
        new_scope: str,
        target_group: str | None = None,
        actor_id: str = "user",
    ) -> bool:
        """
        Promote 记忆到更高作用域。
        PowerMem 的规则：只能向更严格的方向（数值更大）移动。
        """
        for mem in self._store:
            if mem["id"] == memory_id:
                old_scope = mem["scope"]
                if SCOPE_LEVEL.get(new_scope, 0) <= SCOPE_LEVEL.get(old_scope, 0):
                    print(f"    [!] 不能从 {old_scope} promote 到 {new_scope}（只能向更开放的方向）")
                    return False

                mem["scope"] = new_scope
                if target_group:
                    mem["target_group"] = target_group
                mem["scope_history"].append({
                    "scope": new_scope,
                    "changed_at": datetime.now().isoformat(),
                    "actor": actor_id,
                })

                self._audit_log.append({
                    "memory_id": memory_id,
                    "old_scope": old_scope,
                    "new_scope": new_scope,
                    "actor": actor_id,
                    "timestamp": datetime.now().isoformat(),
                })
                return True
        return False

    def search_for_agent(
        self,
        query: str,
        user_id: str,
        agent_id: str,
    ) -> list:
        """
        检索时考虑 scope：
        - PRIVATE: 仅 owner agent 可见
        - AGENT_GROUP: owner + 同组 agent 可见
        - PUBLIC: 所有 agent 可见
        """
        agent_info = next((a for a in self._agents if a["agent_id"] == agent_id), None)
        agent_group = agent_info["agent_group"] if agent_info else None

        results = []
        query_lower = query.lower()

        for mem in self._store:
            if mem["user_id"] != user_id:
                continue
            if not mem["is_active"]:
                continue

            # Scope 可见性判断
            if mem["scope"] == "PRIVATE" and mem["agent_id"] != agent_id:
                continue  # 其他 agent 看不到 PRIVATE
            if mem["scope"] == "AGENT_GROUP":
                target_group = mem.get("target_group", "")
                if mem["agent_id"] != agent_id and agent_group != target_group:
                    continue  # 不在同一组
            # PUBLIC 不做限制

            # 简单关键词匹配
            content_lower = mem["content"].lower()
            keywords = query_lower.split()
            relevance = sum(1 for kw in keywords if kw in content_lower) / max(len(keywords), 1)

            if relevance > 0:
                results.append({**mem, "relevance": relevance})

        results.sort(key=lambda x: x["relevance"], reverse=True)
        return results

    def get_audit_log(self, memory_id: str | None = None) -> list:
        if memory_id:
            return [e for e in self._audit_log if e["memory_id"] == memory_id]
        return self._audit_log


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(script_dir, "fixtures", "agents.json"), "r", encoding="utf-8") as f:
        config = json.load(f)
    with open(os.path.join(script_dir, "fixtures", "shared_profile.json"), "r", encoding="utf-8") as f:
        profile = json.load(f)

    user_id = config["user_id"]
    store = MemoryWithScope(config)

    print("=" * 85)
    print("X1-8 权限提升与共享")
    print(f"{'=' * 85}")

    # 场景设置：代码助手写入技术偏好（PRIVATE）
    agent_dev = config["agents"][0]  # agent_code_assistant (dev_tools group)
    agent_pm = config["agents"][3]   # agent_project_manager (dev_tools group)
    agent_life = config["agents"][1]  # agent_life_assistant (life_tools group)

    mid1 = store.add(
        "用户是高级后端工程师，主力语言 Go，有 8 年经验",
        user_id, agent_dev["agent_id"], scope="PRIVATE"
    )
    mid2 = store.add(
        "用户偏好简洁的代码风格，不喜欢过多注释",
        user_id, agent_dev["agent_id"], scope="PRIVATE"
    )
    mid3 = store.add(
        "用户对花生过敏，所有食物建议必须避开",
        user_id, agent_life["agent_id"], scope="PRIVATE"
    )
    print(f"\n初始状态：3 条记忆均为 PRIVATE")

    # Promote 前：PM Agent 看不到代码助手的记忆
    print(f"\n{'-' * 85}")
    print("Promote 前：项目管理助手搜索「代码 风格」")
    print(f"{'-' * 85}")
    results_before = store.search_for_agent("代码 风格 技术栈", user_id, agent_pm["agent_id"])
    if not results_before:
        print(f"  (无结果) → 正确！PM Agent 看不到代码助手的 PRIVATE 记忆")
    else:
        for r in results_before:
            print(f"  [{r['id']}] {r['content']}")

    # Promote：技术身份 → AGENT_GROUP (dev_tools)
    print(f"\n{'-' * 85}")
    print("Promote 操作")
    print(f"{'-' * 85}")
    for promo in profile["promotable_memories"][:2]:  # 前两条是 dev_tools 的
        # 用「关键字符重合度」做匹配，避免子串不一致导致 promote 失败
        # 取 promo.content 中前 8 个字符作为指纹（足够区分不同记忆）
        promo_fingerprint = promo["content"][:8]
        target_mem = next(
            (m for m in store._store
             if promo_fingerprint in m["content"]  # 用前缀匹配，允许中间有插入语
             and m["agent_id"] == agent_dev["agent_id"]),
            None,
        )
        if target_mem:
            ok = store.promote(
                target_mem["id"],
                promo["suggested_scope"],
                promo["target_group"],
                actor_id="user",
            )
            if ok:
                print(f"  [v] [{target_mem['id']}] {promo['suggested_scope']} "
                      f"(target={promo['target_group']}) ← {promo['reason']}")
        else:
            print(f"  [!] 未找到匹配记忆：{promo['content']}")

    # Promote 后：PM Agent 现在能看到代码助手的 AGENT_GROUP 记忆
    print(f"\n{'-' * 85}")
    print("Promote 后：项目管理助手搜索「代码 风格」")
    print(f"{'-' * 85}")
    results_after = store.search_for_agent("代码 风格 技术栈", user_id, agent_pm["agent_id"])
    for r in results_after:
        print(f"  [{r['id']}] (scope={r['scope']}) {r['content']}")
    print(f"  共 {len(results_after)} 条 → PM Agent 现在可以看到同组的 AGENT_GROUP 记忆")

    # 跨组验证：生活助手看不到 dev_tools 组的记忆
    print(f"\n{'-' * 85}")
    print("跨组验证：生活助手搜索「代码 风格 技术栈」")
    print(f"{'-' * 85}")
    cross_results = store.search_for_agent("代码 风格 技术栈", user_id, agent_life["agent_id"])
    if not cross_results:
        print(f"  (无结果) → 正确！life_tools 组的 Agent 看不到 dev_tools 组的记忆")
    else:
        for r in cross_results:
            print(f"  [{r['id']}] {r['content']}")

    # 审计日志
    print(f"\n{'-' * 85}")
    print("审计日志")
    print(f"{'-' * 85}")
    for entry in store.get_audit_log():
        print(f"  [{entry['timestamp'][:19]}] {entry['memory_id']}: "
              f"{entry['old_scope']} → {entry['new_scope']} (by {entry['actor']})")

    print(f"\n  关键观察：")
    print(f"    1. 记忆默认 PRIVATE，写入后仅 owner Agent 可见")
    print(f"    2. promote 到 AGENT_GROUP 后，同组 Agent 可检索")
    print(f"    3. 跨 Agent Group 不可见（life_tools 看不到 dev_tools 的记忆）")
    print(f"    4. scope 变更全程记录审计日志，可追溯 '谁、何时、为什么'")
    print()


if __name__ == "__main__":
    main()
