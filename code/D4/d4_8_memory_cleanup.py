"""
d4_8：长期记忆定期清理

演示：
  1. calc_retention：简化保留率，驱动生命周期决策
  2. cleanup_memories：dry-run 先观测，再真正归档 / 硬删
  3. 保护字段永不硬删；硬删走主库 + 向量 + 缓存级联清理
  4. 清理作业按 user_id 隔离，避免批量任务串户

对应课程：D4 第六部分「定期清理」
对应 Issue：datawhalechina/easy-data-x-ai#32

运行：
  python d4_8_memory_cleanup.py

无需外部 API / seekdb，纯 Python 即可跑通。
"""

from __future__ import annotations

import math
import uuid
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Iterator


# ---------- 1. 带级联索引的记忆存储 ----------

@dataclass
class MemoryItem:
    id: str
    content: str
    user_id: str
    created_at: datetime
    last_accessed_at: datetime
    access_count: int = 0
    protected: bool = False
    archived: bool = False


@dataclass
class LifecycleMemoryStore:
    """
    模拟主库 + 向量索引 + 缓存。
    硬删除必须三级联，避免幽灵记忆。
    """

    records: dict[str, MemoryItem] = field(default_factory=dict)
    vector_index: set[str] = field(default_factory=set)
    cache: dict[str, str] = field(default_factory=dict)
    archive: dict[str, MemoryItem] = field(default_factory=dict)
    def add(
        self,
        content: str,
        user_id: str,
        *,
        created_at: datetime,
        last_accessed_at: datetime | None = None,
        access_count: int = 0,
        protected: bool = False,
    ) -> MemoryItem:
        mem_id = str(uuid.uuid4())
        item = MemoryItem(
            id=mem_id,
            content=content,
            user_id=user_id,
            created_at=created_at,
            last_accessed_at=last_accessed_at or created_at,
            access_count=access_count,
            protected=protected,
        )
        self.records[mem_id] = item
        self.vector_index.add(mem_id)
        self.cache[mem_id] = content
        return deepcopy(item)

    def iter_all(self, user_id: str) -> Iterator[MemoryItem]:
        """按用户范围读取生命周期记忆，并返回副本。"""
        if not user_id or not user_id.strip():
            raise ValueError("user_id is required for memory reads")
        for item in self.records.values():
            if item.user_id == user_id:
                yield deepcopy(item)

    def archive_memory(self, memory_id: str) -> None:
        item = self.records.get(memory_id)
        if item is None:
            return
        item.archived = True
        self.archive[memory_id] = item
        self.drop_from_hot_index(memory_id)

    def drop_from_hot_index(self, memory_id: str) -> None:
        self.vector_index.discard(memory_id)
        self.cache.pop(memory_id, None)

    def delete(self, memory_id: str, requester_id: str) -> bool:
        """仅所有者可硬删；受保护记忆只能归档，不能直接删除。"""
        if not requester_id or not requester_id.strip():
            raise ValueError("requester_id is required for memory deletion")
        item = self.records.get(memory_id)
        if item is None:
            return False
        if item.user_id != requester_id:
            raise PermissionError(
                f"User {requester_id} cannot delete memory owned by {item.user_id}"
            )
        if item.protected:
            raise PermissionError(f"Protected memory {memory_id} cannot be deleted")

        self.records.pop(memory_id, None)
        self.archive.pop(memory_id, None)
        self.vector_index.discard(memory_id)
        self.cache.pop(memory_id, None)
        return True

    def searchable_ids(self) -> set[str]:
        return set(self.vector_index)


# ---------- 2. 保留率与清理作业（对齐课程伪代码）----------

def calc_retention(mem: MemoryItem, now: datetime, half_life_days: float = 30.0) -> float:
    """R ≈ exp(-age/half_life) + 访问强化，裁剪到 [0, 1]"""
    age_days = max(0.0, (now - mem.created_at).total_seconds() / 86400)
    idle_boost_anchor = mem.last_accessed_at
    idle_days = max(0.0, (now - idle_boost_anchor).total_seconds() / 86400)
    # 用“距上次访问”更贴近遗忘曲线：长期不用则更快掉
    recency = math.exp(-idle_days / half_life_days)
    bonus = min(0.25, mem.access_count * 0.04)
    # created 很久但最近刚访问过时，recency 仍然高
    _ = age_days  # 保留字段便于后续扩展写入龄期策略
    return max(0.0, min(1.0, recency + bonus))


def cleanup_memories(
    store: LifecycleMemoryStore,
    now: datetime,
    *,
    user_id: str,
    dry_run: bool = True,
) -> dict[str, Any]:
    """
    定期清理作业。
    dry_run=True 时只统计将要发生的动作，便于先观测再真正删除。
    """
    if not user_id or not user_id.strip():
        raise ValueError("user_id is required for scoped memory cleanup")

    stats = {"archived": 0, "deleted": 0, "kept": 0, "protected_skipped": 0}
    actions: list[str] = []

    for mem in list(store.iter_all(user_id=user_id)):
        retention = calc_retention(mem, now)
        idle_days = (now - mem.last_accessed_at).days
        protected = mem.protected

        # 1) 硬淘汰：极低价值且长期零唤醒
        if (not protected) and retention < 0.1 and idle_days >= 90:
            stats["deleted"] += 1
            actions.append(f"DELETE {mem.id} R={retention:.2f} idle={idle_days}d")
            if not dry_run:
                store.delete(mem.id, requester_id=user_id)
            continue

        # 归档项仍需检查硬淘汰条件，但不重复归档或计入热记忆。
        if mem.archived:
            continue

        # 保护字段若已达硬删条件：跳过删除，最多归档
        if protected and retention < 0.1 and idle_days >= 90:
            stats["protected_skipped"] += 1
            stats["archived"] += 1
            actions.append(f"ARCHIVE(protected) {mem.id}")
            if not dry_run:
                store.archive_memory(mem.id)
            continue

        # 2) 软淘汰：移出日常检索，保留可追溯归档
        if retention < 0.3 or idle_days >= 30:
            stats["archived"] += 1
            actions.append(f"ARCHIVE {mem.id} R={retention:.2f} idle={idle_days}d")
            if not dry_run:
                store.archive_memory(mem.id)
            continue

        # 3) 仍可用
        stats["kept"] += 1
        actions.append(f"KEEP {mem.id} R={retention:.2f} idle={idle_days}d")

    return {**stats, "actions": actions}


# ---------- 3. 演示与断言 ----------

def seed_store(now: datetime) -> LifecycleMemoryStore:
    store = LifecycleMemoryStore()

    store.add(
        "primary_language=Python",
        user_id="alice",
        created_at=now - timedelta(days=200),
        last_accessed_at=now - timedelta(days=120),
        access_count=0,
        protected=True,
    )
    store.add(
        "用户偏好简洁回答",
        user_id="alice",
        created_at=now - timedelta(days=10),
        last_accessed_at=now - timedelta(days=1),
        access_count=8,
    )
    store.add(
        "临时：今天喝了咖啡",
        user_id="alice",
        created_at=now - timedelta(days=40),
        last_accessed_at=now - timedelta(days=35),
        access_count=0,
    )
    store.add(
        "过时：试用过已废弃的小众框架",
        user_id="alice",
        created_at=now - timedelta(days=200),
        last_accessed_at=now - timedelta(days=150),
        access_count=0,
    )
    # Bob 的记忆：清理 Alice 时不应被误伤
    store.add(
        "Bob 是 Java 开发者",
        user_id="bob",
        created_at=now - timedelta(days=200),
        last_accessed_at=now - timedelta(days=150),
        access_count=0,
    )
    return store


def demo_dry_run(store: LifecycleMemoryStore, now: datetime) -> dict[str, Any]:
    print("=" * 64)
    print("实验 1：先 dry-run，再决定是否真正清理")
    print("=" * 64)

    stats = cleanup_memories(store, now, user_id="alice", dry_run=True)
    print(f"\n  dry-run 统计：archived={stats['archived']} deleted={stats['deleted']} "
          f"kept={stats['kept']} protected_skipped={stats['protected_skipped']}")
    print("  动作清单：")
    for action in stats["actions"]:
        print(f"    - {action}")

    # dry-run 不应改存储
    assert len(store.records) == 5
    assert len(store.vector_index) == 5
    assert stats["deleted"] >= 1
    assert stats["archived"] >= 1
    assert stats["kept"] >= 1
    assert stats["protected_skipped"] >= 1
    print("  → 正确：dry-run 只观测，不改主库 / 索引")
    return stats


def demo_apply_cleanup(store: LifecycleMemoryStore, now: datetime) -> None:
    print("\n" + "=" * 64)
    print("实验 2：真正执行清理（级联 + 保护字段）")
    print("=" * 64)

    stats = cleanup_memories(store, now, user_id="alice", dry_run=False)
    print(
        f"\n  执行统计：archived={stats['archived']} deleted={stats['deleted']} "
        f"kept={stats['kept']} protected_skipped={stats['protected_skipped']}"
    )

    # 硬删目标应从三级联消失
    deleted_content = "过时：试用过已废弃的小众框架"
    assert not any(item.content == deleted_content for item in store.records.values())
    assert not any(item.content == deleted_content for item in store.archive.values())

    # 保护字段不能被硬删，最多归档
    protected = next(item for item in store.archive.values() if item.protected)
    assert protected.content == "primary_language=Python"
    assert protected.id not in store.vector_index
    assert protected.id not in store.cache
    print(f"  保护字段已归档且退出热索引：[{protected.id}]")

    # 活跃记忆保留且仍可检索
    active = next(item for item in store.records.values() if "简洁" in item.content)
    assert active.id in store.vector_index
    assert active.archived is False
    print(f"  活跃记忆仍保留：[{active.id}] {active.content}")

    # 幽灵记忆检查：索引里不能有主库没有的 id
    ghosts = store.vector_index - set(store.records.keys())
    assert not ghosts, f"ghost vectors found: {ghosts}"
    print("  → 正确：硬删级联清理；保护字段只归档；无幽灵索引")


def demo_user_isolation(store: LifecycleMemoryStore, now: datetime) -> None:
    print("\n" + "=" * 64)
    print("实验 3：清理作业按 user_id 隔离")
    print("=" * 64)

    bob_before = [item for item in store.records.values() if item.user_id == "bob"]
    assert len(bob_before) == 1
    bob_id = bob_before[0].id

    # 再跑一次只清 alice：Bob 的过期记忆仍应留在主库
    cleanup_memories(store, now, user_id="alice", dry_run=False)
    assert store.records.get(bob_id) is not None
    bob_left = [item.content for item in store.records.values() if item.user_id == "bob"]
    print(f"  Bob 记忆仍在主库：{bob_left}")
    print("  → 正确：批量清理必须带命名空间，避免串户误删")


def print_summary() -> None:
    print("\n" + "=" * 64)
    print("总结")
    print("  1. 清理默认先 dry-run，确认动作分布再落盘")
    print("  2. 分级处置：KEEP → ARCHIVE → DELETE，不要二元删留")
    print("  3. 硬删必须级联主库 / 向量 / 缓存")
    print("  4. protected 字段永不硬删；清理作业要带 user_id")
    print("=" * 64)


def main() -> None:
    now = datetime(2026, 7, 25, 12, 0, 0)
    store = seed_store(now)

    print(">>> 已写入 Alice / Bob 的生命周期样例记忆")
    for user_id in ("alice", "bob"):
        for item in store.iter_all(user_id=user_id):
            r = calc_retention(item, now)
            idle = (now - item.last_accessed_at).days
            flag = "protected" if item.protected else "normal"
            print(
                f"    [{item.id}] ({item.user_id}) R={r:.2f} idle={idle}d "
                f"{flag} | {item.content}"
            )

    demo_dry_run(store, now)
    demo_apply_cleanup(store, now)
    demo_user_isolation(store, now)
    print_summary()
    print("\n[PASS] d4_8_memory_cleanup 全部断言通过")


if __name__ == "__main__":
    main()
