"""
x1_5_conflict_resolve.py — 冲突裁决执行：旧版失效、新版写入、版本追溯

本脚本演示 x1_4 检测到冲突后, 如何实际修改记忆库:
  1. UPDATE: 旧版标记 is_active=False (保留历史) → 新版写入，replaces 字段建立追溯链
  2. DELETE: 不物理删除，标记 should_forget=True (检索时 ×0.1 降权，可回滚)
  3. ADD: 直接新增

三个场景演示:
  - 技术栈变更 (Java→Go): UPDATE + 版本链追溯
  - 并存偏好 (喜欢披萨+吃素): ADD，两条独立衰减
  - 直接矛盾 (喜欢披萨→讨厌披萨): DELETE，标记遗忘

运行:
  python x1_5_conflict_resolve.py

关键设计决策:
  - UPDATE 不删旧版 → is_active=False 保留，replaces 字段链接新旧版本
  - DELETE 不物理删除 → should_forget=True 只降权，用户纠正后可回滚
  - 物理删除意味着不可恢复，标记遗忘 = 可逆

对应正文: X1-1 §4.2 "裁决执行：留版本链，不物理删除"
"""

import json
import os
import copy
from datetime import datetime


def resolve_conflict(
    memories_store: list,
    new_fact: str,
    action: str,
    target_id: str | None,
    importance_score: float = 0.5,
    memory_type: str = "short_term",
) -> dict:
    """
    执行冲突裁决，更新记忆库。
    返回执行的操作摘要。
    """
    now = datetime.now().isoformat()
    result = {
        "action": action,
        "new_fact": new_fact,
        "timestamp": now,
        "changes": [],
    }

    if action == "UPDATE" and target_id:
        # 旧版标记为 inactive
        for mem in memories_store:
            if mem["id"] == target_id:
                old_content = mem["content"]
                mem["is_active"] = False
                mem["updated_at"] = now
                result["changes"].append({
                    "type": "DEACTIVATE",
                    "id": target_id,
                    "old_content": old_content,
                })
                break

        # 写入新版本
        new_id = f"mem_{len(memories_store) + 1:03d}"
        new_memory = {
            "id": new_id,
            "content": new_fact,
            "importance_score": importance_score,
            "memory_type": memory_type,
            "created_at": now,
            "last_reviewed": now,
            "access_count": 0,
            "is_active": True,
            "replaces": target_id,
        }
        memories_store.append(new_memory)
        result["changes"].append({
            "type": "CREATE",
            "id": new_id,
            "content": new_fact,
        })

    elif action == "DELETE" and target_id:
        for mem in memories_store:
            if mem["id"] == target_id:
                mem["is_active"] = False
                mem["should_forget"] = True
                mem["updated_at"] = now
                result["changes"].append({
                    "type": "MARK_FORGET",
                    "id": target_id,
                    "old_content": mem["content"],
                })
                break

    elif action == "ADD":
        new_id = f"mem_{len(memories_store) + 1:03d}"
        new_memory = {
            "id": new_id,
            "content": new_fact,
            "importance_score": importance_score,
            "memory_type": memory_type,
            "created_at": now,
            "last_reviewed": now,
            "access_count": 0,
            "is_active": True,
        }
        memories_store.append(new_memory)
        result["changes"].append({
            "type": "CREATE",
            "id": new_id,
            "content": new_fact,
        })

    return result


def show_memory_state(memories: list, title: str, filter_ids: list[str] | None = None):
    """格式化展示记忆库状态"""
    print(f"\n  [{title}]")
    print(f"  {'ID':<10} {'Active':<8} {'Forget':<8} {'内容':<55}")
    print(f"  {'-' * 80}")
    for mem in memories:
        if filter_ids and mem["id"] not in filter_ids:
            continue
        active = "[v]" if mem.get("is_active", True) else "[x]"
        forget = "[v]" if mem.get("should_forget", False) else "[x]"
        content = mem["content"][:52]
        print(f"  {mem['id']:<10} {active:<8} {forget:<8} {content}")


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    fixtures_path = os.path.join(script_dir, "fixtures", "sample_memories.json")
    with open(fixtures_path, "r", encoding="utf-8") as f:
        original_data = json.load(f)

    # 使用深拷贝，避免修改原 fixtures
    store = copy.deepcopy(original_data["memories"])

    # 场景 1：技术栈变更 — UPDATE
    print("=" * 85)
    print("X1-5 冲突裁决执行")
    print(f"{'=' * 85}")

    print("\n场景 1：技术栈变更（UPDATE）")
    print("  新事实: 「用户已从 Java 全面转向 Go 语言开发」")
    print("  目标: mem_009（用户目前主要使用 Java 开发后端服务）")

    related_ids = ["mem_009"]
    show_memory_state(store, "操作前", related_ids)

    result1 = resolve_conflict(
        store,
        "用户已从 Java 全面转向 Go 语言开发",
        action="UPDATE",
        target_id="mem_009",
        importance_score=0.82,
        memory_type="long_term",
    )
    new_id = next(c["id"] for c in result1["changes"] if c["type"] == "CREATE")
    show_memory_state(store, "操作后", related_ids + [new_id])

    # 场景 2：并存偏好 — ADD
    print("\n场景 2：并存偏好（ADD）")
    print("  新事实: 「用户最近在吃素，不吃任何肉类」")
    print("  冲突: mem_007（用户最喜欢吃披萨）→ 但不是矛盾，并存")

    related_ids2 = ["mem_007"]
    show_memory_state(store, "操作前", related_ids2)

    result2 = resolve_conflict(
        store,
        "用户最近在吃素，不吃任何肉类",
        action="ADD",
        target_id=None,
        importance_score=0.50,
    )
    new_id2 = next(c["id"] for c in result2["changes"] if c["type"] == "CREATE")
    show_memory_state(store, "操作后（两条并存）", related_ids2 + [new_id2])

    # 场景 3：直接矛盾 — DELETE
    print("\n场景 3：直接矛盾（DELETE）")
    print("  新事实: 「用户非常讨厌披萨，从来不吃」")
    print("  目标: mem_007（用户最喜欢吃披萨）→ 直接矛盾，删除旧的")

    related_ids3 = ["mem_007"]
    show_memory_state(store, "操作前", related_ids3)

    result3 = resolve_conflict(
        store,
        "用户非常讨厌披萨，从来不吃",
        action="DELETE",
        target_id="mem_007",
    )
    show_memory_state(store, "操作后", related_ids3)
    print(f"\n  注意：记忆未被物理删除，只是标记 should_forget=True、is_active=False")
    print(f"  检索时 final_score 会乘以 forgotten_score_multiplier (0.1) 大幅降权")

    # 展示最终状态
    print(f"\n{'=' * 85}")
    print("最终记忆库状态（涉及变更的记忆）")
    changed_ids = ["mem_009", new_id, "mem_007", new_id2]
    show_memory_state(store, "变更后", changed_ids)

    print(f"\n  关键观察：")
    print(f"    1. mem_009 (Java) → is_active=False，新记忆 {new_id} (Go) → is_active=True")
    print(f"    2. mem_007 (喜欢披萨) → 场景 2 中保留，场景 3 中被标记遗忘")
    print(f"    3. 历史版本不删除，可溯源 '用户什么时候开始用 Go？'")
    print()


if __name__ == "__main__":
    main()
