"""
d4_5：多用户 / 多租户记忆隔离

演示：
  1. user_id 命名空间：写入带标签，检索带过滤（查询构建阶段隔离）
  2. 权限校验：所有者可删改，非所有者越权操作被拒绝
  3. 显式分享：未授权不可读；授权后仅按权限放行

对应课程：D4 第五部分「多用户 / 多租户记忆隔离」
对应 Issue：datawhalechina/easy-data-x-ai#33

设计对齐 PowerMem：
  - storage/adapter.py 的 _SYSTEM_FILTER_KEYS / _build_db_filters
  - MultiUserMemoryManager 的所有权与 PermissionError
  - 过滤发生在查询构建阶段，而不是检索后再筛

运行：
  python d4_5_multi_user_isolation.py

无需外部 API / seekdb，纯 Python 即可跑通。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


# ---------- 1. 数据模型 ----------

@dataclass
class MemoryRecord:
    """一条带命名空间与权限元数据的记忆"""

    id: str
    content: str
    user_id: str
    agent_id: str = "tech_assistant"
    run_id: str = "default"
    shared_with: dict[str, list[str]] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


# ---------- 2. 带隔离与权限门的记忆存储 ----------

class IsolatedMemoryStore:
    """
    模拟 PowerMem 多用户记忆隔离。

    核心约定：
      - 检索：user_id（必选）在遍历第一步就过滤
      - 写删：先校验所有权 / 显式授权，再改数据
    """

    def __init__(self) -> None:
        self._store: list[MemoryRecord] = []
        self._seq = 0

    def add(
        self,
        content: str,
        user_id: str,
        agent_id: str = "tech_assistant",
        run_id: str = "default",
    ) -> MemoryRecord:
        """写入记忆：必须绑定 user_id 命名空间"""
        if not user_id:
            raise ValueError("user_id is required for multi-tenant isolation")

        self._seq += 1
        record = MemoryRecord(
            id=f"mem_{self._seq:03d}",
            content=content,
            user_id=user_id,
            agent_id=agent_id,
            run_id=run_id,
        )
        self._store.append(record)
        return record

    def search(
        self,
        query: str,
        user_id: str,
        agent_id: str | None = None,
    ) -> list[MemoryRecord]:
        """
        检索记忆。

        关键：user_id 在查询构建阶段注入过滤条件。
        对应 PowerMem 的 _build_db_filters，而不是“全量搜完再丢弃”。
        显式分享且授予 read/write 的记忆，可在查询阶段一并纳入可见范围。
        """
        if not user_id:
            raise ValueError("user_id is required; refusing unscoped search")

        keywords = [kw for kw in query.lower().split() if kw]
        results: list[tuple[float, MemoryRecord]] = []

        for mem in self._store:
            # 一级隔离：本人命名空间，或已被显式授予读权限
            if mem.user_id != user_id and not self._can_read(mem, user_id):
                continue
            # 二级隔离（可选）：同一用户下按 agent 再切
            if agent_id is not None and mem.agent_id != agent_id:
                continue

            score = self._relevance(mem.content, keywords)
            if score > 0:
                results.append((score, mem))

        results.sort(key=lambda item: item[0], reverse=True)
        return [mem for _, mem in results]

    def get(self, memory_id: str) -> MemoryRecord | None:
        for mem in self._store:
            if mem.id == memory_id:
                return mem
        return None

    def check_permission(
        self,
        memory_id: str,
        requester_id: str,
        permission: str,
    ) -> bool:
        """检查 requester 对某条记忆是否具备指定权限"""
        mem = self.get(memory_id)
        if mem is None:
            return False
        if mem.user_id == requester_id:
            return True
        granted = mem.shared_with.get(requester_id, [])
        if permission in granted:
            return True
        # write 蕴含 read：仅授予 write 时也应可读
        if permission == "read" and "write" in granted:
            return True
        return False

    def share(
        self,
        memory_id: str,
        owner_id: str,
        target_user_id: str,
        permissions: list[str] | None = None,
    ) -> dict[str, Any]:
        """所有者显式分享记忆给其他用户"""
        mem = self._require_owned(memory_id, owner_id)
        perms = permissions or ["read"]
        mem.shared_with[target_user_id] = list(perms)
        return {
            "success": True,
            "memory_id": memory_id,
            "shared_from": owner_id,
            "shared_with": target_user_id,
            "permissions": perms,
        }

    def update(
        self,
        memory_id: str,
        requester_id: str,
        new_content: str,
    ) -> dict[str, Any]:
        """更新记忆：所有者，或被授予 write 的用户"""
        mem = self.get(memory_id)
        if mem is None:
            raise ValueError(f"Memory {memory_id} not found")

        if not self.check_permission(memory_id, requester_id, "write"):
            raise PermissionError(
                f"User {requester_id} cannot update memory owned by {mem.user_id}"
            )

        mem.content = new_content
        return {"success": True, "id": memory_id, "memory": new_content}

    def delete(self, memory_id: str, requester_id: str) -> dict[str, Any]:
        """删除记忆：仅所有者可以删除（对齐 MultiUserMemoryManager）"""
        mem = self._require_owned(memory_id, requester_id)
        self._store = [item for item in self._store if item.id != mem.id]
        return {
            "success": True,
            "deleted_id": memory_id,
            "deleted_by": requester_id,
        }

    def get_all_for_user(self, user_id: str) -> list[MemoryRecord]:
        """调试用：列出某用户命名空间内的全部记忆"""
        return [mem for mem in self._store if mem.user_id == user_id]

    def search_without_isolation(self, query: str) -> list[MemoryRecord]:
        """反例：去掉 user_id 过滤，演示串户风险（仅用于对比，生产禁用）"""
        keywords = [kw for kw in query.lower().split() if kw]
        return [
            mem for mem in self._store
            if self._relevance(mem.content, keywords) > 0
        ]

    def _require_owned(self, memory_id: str, requester_id: str) -> MemoryRecord:
        mem = self.get(memory_id)
        if mem is None:
            raise ValueError(f"Memory {memory_id} not found")
        if mem.user_id != requester_id:
            raise PermissionError(
                f"User {requester_id} does not own memory {memory_id} "
                f"(owner={mem.user_id})"
            )
        return mem

    @staticmethod
    def _can_read(mem: MemoryRecord, requester_id: str) -> bool:
        granted = mem.shared_with.get(requester_id, [])
        return "read" in granted or "write" in granted

    @staticmethod
    def _relevance(content: str, keywords: list[str]) -> float:
        if not keywords:
            return 0.0
        lower = content.lower()
        hits = sum(1 for kw in keywords if kw in lower)
        return hits / len(keywords)


# ---------- 3. 演示步骤（拆成小函数，便于对照课程正文）----------

def seed_users(store: IsolatedMemoryStore) -> dict[str, list[MemoryRecord]]:
    """为 Alice / Bob 写入各自命名空间的记忆"""
    alice_memories = [
        store.add("Alice 是 Python 开发者，喜欢简洁回答", user_id="alice"),
        store.add("Alice 对花生过敏，饮食建议必须避开", user_id="alice"),
        store.add("Alice 团队前端使用 React", user_id="alice"),
    ]
    bob_memories = [
        store.add("Bob 是 Java 开发者，喜欢详细解释", user_id="bob"),
        store.add("Bob 公司技术栈以 Spring Boot 为主", user_id="bob"),
    ]
    return {"alice": alice_memories, "bob": bob_memories}


def demo_namespace_isolation(store: IsolatedMemoryStore) -> None:
    print("=" * 64)
    print("实验 1：user_id 命名空间隔离")
    print("=" * 64)

    alice_hits = store.search("Web 框架 Python", user_id="alice")
    bob_hits = store.search("Web 框架 Java", user_id="bob")

    print("\n[Alice 检索] query='Web 框架 Python'")
    for mem in alice_hits:
        print(f"  - [{mem.id}] ({mem.user_id}) {mem.content}")
    print(f"  → 共 {len(alice_hits)} 条，全部属于 alice")

    print("\n[Bob 检索] query='Web 框架 Java'")
    for mem in bob_hits:
        print(f"  - [{mem.id}] ({mem.user_id}) {mem.content}")
    print(f"  → 共 {len(bob_hits)} 条，全部属于 bob")

    # 交叉探测：Alice 搜 Bob 领域关键词，不应命中 Bob 的记忆
    cross = store.search("花生 过敏", user_id="bob")
    print("\n[交叉验证] Bob 搜索「花生 过敏」（Alice 的隐私领域）")
    if not cross:
        print("  (无结果) → 正确：Bob 看不到 Alice 的过敏信息")
    else:
        print(f"  [!] 串户：Bob 看到了 {len(cross)} 条不该看见的记忆")
        raise AssertionError("namespace isolation failed")

    # 反例对比
    leaked = store.search_without_isolation("花生 过敏")
    print("\n[反例] 去掉 user_id 过滤后再搜「花生 过敏」")
    for mem in leaked:
        print(f"  - [{mem.id}] ({mem.user_id}) {mem.content}")
    print("  → 这就是串户：敏感信息离开了命名空间边界")


def demo_permission_guard(
    store: IsolatedMemoryStore,
    alice_memories: list[MemoryRecord],
) -> None:
    print("\n" + "=" * 64)
    print("实验 2：权限校验（越权删除 / 合法删除）")
    print("=" * 64)

    target = alice_memories[0]
    print(f"\n目标记忆：[{target.id}] {target.content}")

    print("\n[越权] Bob 尝试删除 Alice 的记忆")
    try:
        store.delete(target.id, requester_id="bob")
        print("  [!] 失败：越权删除竟然成功了")
        raise AssertionError("permission guard failed")
    except PermissionError as exc:
        print(f"  PermissionError → {exc}")
        print("  → 正确：非所有者删除被拒绝")

    still_there = store.get(target.id)
    assert still_there is not None, "memory should still exist after denied delete"
    print(f"  记忆仍在：[{still_there.id}]")

    print("\n[合法] Alice 删除自己的一条记忆")
    result = store.delete(target.id, requester_id="alice")
    print(f"  删除成功：{result}")
    assert store.get(target.id) is None


def demo_explicit_share(
    store: IsolatedMemoryStore,
    alice_memories: list[MemoryRecord],
) -> None:
    print("\n" + "=" * 64)
    print("实验 3：显式分享 + 最小权限")
    print("=" * 64)

    # alice_memories[0] 已在实验 2 删除，取下一条
    shared = alice_memories[1]
    print(f"\nAlice 将 [{shared.id}] 以 read 权限分享给 Bob")
    share_result = store.share(
        memory_id=shared.id,
        owner_id="alice",
        target_user_id="bob",
        permissions=["read"],
    )
    print(f"  share → {share_result}")

    can_read = store.check_permission(shared.id, "bob", "read")
    can_write = store.check_permission(shared.id, "bob", "write")
    print(f"\n  Bob 读权限：{can_read}")
    print(f"  Bob 写权限：{can_write}")
    assert can_read is True
    assert can_write is False

    # 分享后：读路径在查询构建阶段放行（对齐权限表「已显式分享 → 可读/搜」）
    bob_shared_hits = store.search("花生 过敏", user_id="bob")
    print("\n[授权后检索] Bob 再搜「花生 过敏」")
    for mem in bob_shared_hits:
        print(f"  - [{mem.id}] ({mem.user_id}) {mem.content}")
    assert any(mem.id == shared.id for mem in bob_shared_hits), (
        "shared read should be visible in search"
    )
    print("  → 正确：显式分享后，Bob 可按 read 权限检索到该记忆")

    print("\n[越权] Bob 仅有 read，尝试 update")
    try:
        store.update(shared.id, requester_id="bob", new_content="被篡改的内容")
        raise AssertionError("write should be denied for read-only share")
    except PermissionError as exc:
        print(f"  PermissionError → {exc}")
        print("  → 正确：分享 read 不等于可以改")


def print_summary(store: IsolatedMemoryStore) -> None:
    print("\n" + "=" * 64)
    print("当前各用户命名空间快照")
    print("=" * 64)
    for user_id in ("alice", "bob"):
        memories = store.get_all_for_user(user_id)
        print(f"\n  [{user_id}] 共 {len(memories)} 条")
        for mem in memories:
            shared = (
                f" shared={list(mem.shared_with.keys())}"
                if mem.shared_with
                else ""
            )
            print(f"    - [{mem.id}] {mem.content}{shared}")

    print("\n" + "=" * 64)
    print("总结")
    print("  1. 多用户记忆必须用 user_id 做命名空间，检索时一并过滤")
    print("  2. 过滤应发生在查询构建阶段，而不是检索后再丢弃")
    print("  3. 删改要做所有权 / 授权校验，越权必须显式失败")
    print("  4. 跨用户可见只能走显式分享，且按最小权限放行")
    print("=" * 64)


def main() -> None:
    store = IsolatedMemoryStore()
    seeded = seed_users(store)

    print(">>> 已为 Alice / Bob 写入各自命名空间的记忆")
    print(f"    Alice: {len(seeded['alice'])} 条")
    print(f"    Bob:   {len(seeded['bob'])} 条")

    demo_namespace_isolation(store)
    demo_permission_guard(store, seeded["alice"])
    demo_explicit_share(store, seeded["alice"])
    print_summary(store)


if __name__ == "__main__":
    main()
