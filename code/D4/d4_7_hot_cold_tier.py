"""
d4_7：长期记忆冷热分层

演示：
  1. assign_tier：按保留率 + 访问新鲜度分流到 hot / warm / cold
  2. migrate_if_needed：降温归档（移出热索引）与回热唤醒
  3. 日常检索只扫热/温面，冷层默认不进候选
  4. 降权决定排序先后，分层决定是否留在热检索面

对应课程：D4 第六部分「冷热分层」
对应 Issue：datawhalechina/easy-data-x-ai#32

运行：
  python d4_7_hot_cold_tier.py

无需外部 API / seekdb，纯 Python 即可跑通。
"""

from __future__ import annotations

import math
import uuid
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Literal

Tier = Literal["hot", "warm", "cold"]


# ---------- 1. 数据模型 ----------

@dataclass
class TieredMemory:
    id: str
    content: str
    user_id: str
    retention: float
    days_since_access: int
    is_profile: bool = False
    tier: Tier = "hot"
    in_hot_index: bool = True


@dataclass
class TieredMemoryStore:
    """
    模拟热 / 温 / 冷三层记忆存储。

    - hot/warm：在线可检索（热检索面）
    - cold：归档表，默认不进日常 search
    """

    memories: dict[str, TieredMemory] = field(default_factory=dict)
    archive: dict[str, TieredMemory] = field(default_factory=dict)
    def add(
        self,
        content: str,
        user_id: str,
        retention: float,
        days_since_access: int,
        is_profile: bool = False,
    ) -> TieredMemory:
        mem = TieredMemory(
            id=str(uuid.uuid4()),
            content=content,
            user_id=user_id,
            retention=retention,
            days_since_access=days_since_access,
            is_profile=is_profile,
        )
        mem.tier = assign_tier(mem, mem.retention, mem.days_since_access)
        mem.in_hot_index = mem.tier != "cold"
        if mem.tier == "cold":
            self.archive[mem.id] = mem
        else:
            self.memories[mem.id] = mem
        return deepcopy(mem)

    def get(self, memory_id: str, requester_id: str) -> TieredMemory | None:
        """仅所有者可按 ID 读取；返回副本，避免绕过迁移规则修改存储。"""
        if not requester_id:
            raise ValueError("requester_id is required for memory reads")
        mem = self._find(memory_id)
        if mem is None:
            return None
        if mem.user_id != requester_id:
            raise PermissionError(
                f"User {requester_id} cannot read memory owned by {mem.user_id}"
            )
        return deepcopy(mem)

    def _find(self, memory_id: str) -> TieredMemory | None:
        """内部迁移路径使用的存储对象查找。"""
        return self.memories.get(memory_id) or self.archive.get(memory_id)

    def search(self, query: str, user_id: str, include_cold: bool = False) -> list[TieredMemory]:
        """日常检索默认只扫热检索面；include_cold=True 表示按需回冷层"""
        keywords = [kw for kw in query.lower().split() if kw]
        pool = list(self.memories.values())
        if include_cold:
            pool.extend(self.archive.values())

        hits: list[tuple[float, TieredMemory]] = []
        for mem in pool:
            if mem.user_id != user_id:
                continue
            if not include_cold and not mem.in_hot_index:
                continue
            score = relevance(mem.content, keywords) * mem.retention
            if score > 0:
                hits.append((score, mem))

        hits.sort(key=lambda item: item[0], reverse=True)
        return [deepcopy(mem) for _, mem in hits]

    def archive_memory(self, memory_id: str) -> None:
        mem = self.memories.pop(memory_id, None)
        if mem is None:
            return
        mem.tier = "cold"
        mem.in_hot_index = False
        self.archive[memory_id] = mem

    def drop_from_hot_index(self, memory_id: str) -> None:
        mem = self._find(memory_id)
        if mem is not None:
            mem.in_hot_index = False

    def restore_to_hot(self, memory_id: str) -> None:
        mem = self.archive.pop(memory_id, None)
        if mem is None:
            mem = self.memories.get(memory_id)
        if mem is None:
            return
        mem.tier = "hot"
        mem.in_hot_index = True
        mem.days_since_access = 0
        mem.retention = max(mem.retention, 0.85)
        self.memories[memory_id] = mem

    def counts_by_tier(self) -> dict[str, int]:
        counts = {"hot": 0, "warm": 0, "cold": 0}
        for mem in list(self.memories.values()) + list(self.archive.values()):
            counts[mem.tier] += 1
        return counts


# ---------- 2. 分层与迁移（对齐课程伪代码）----------

def assign_tier(memory: TieredMemory, retention: float, days_since_access: int) -> Tier:
    """根据保留率与访问新鲜度，决定记忆住哪一层"""
    if memory.is_profile or retention >= 0.7:
        return "hot"
    if retention >= 0.3 and days_since_access <= 30:
        return "warm"
    return "cold"


def migrate_if_needed(store: TieredMemoryStore, memory: TieredMemory) -> str | None:
    """受控同步新指标，并在存储内部原子完成分层迁移。"""
    stored = store._find(memory.id)
    if stored is None:
        return None

    new_retention = memory.retention
    new_days_since_access = memory.days_since_access
    new_tier = assign_tier(stored, new_retention, new_days_since_access)
    old_tier = stored.tier

    # 只同步分层决策允许更新的字段，不接受副本修改所有者或画像标记。
    stored.retention = new_retention
    stored.days_since_access = new_days_since_access
    if new_tier == old_tier:
        return None

    if new_tier == "cold":
        store.memories.pop(stored.id, None)
        store.archive[stored.id] = stored
        stored.in_hot_index = False
    else:
        store.archive.pop(stored.id, None)
        store.memories[stored.id] = stored
        stored.in_hot_index = True

    stored.tier = new_tier
    return f"{old_tier} -> {new_tier}"


def relevance(content: str, keywords: list[str]) -> float:
    if not keywords:
        return 0.0
    lower = content.lower()
    hits = sum(1 for kw in keywords if kw in lower)
    return hits / len(keywords)


def calc_retention(age_days: int, access_count: int, half_life_days: float = 30.0) -> float:
    """简化版时效权重：越新、被访问越多，保留率越高"""
    recency = math.exp2(-age_days / half_life_days)
    bonus = min(0.3, access_count * 0.05)
    return max(0.0, min(1.0, recency + bonus))


# ---------- 3. 演示与断言 ----------

def seed_store() -> TieredMemoryStore:
    store = TieredMemoryStore()
    # 画像：永远热层
    store.add(
        "primary_language=Python",
        user_id="alice",
        retention=0.99,
        days_since_access=2,
        is_profile=True,
    )
    # 高保留率活跃事实 → hot
    store.add(
        "用户偏好简洁回答",
        user_id="alice",
        retention=0.88,
        days_since_access=3,
    )
    # 中等保留、一个月内访问 → warm
    store.add(
        "团队淘汰过 RabbitMQ，觉得运维成本高",
        user_id="alice",
        retention=0.45,
        days_since_access=20,
    )
    # 低保留 + 长期未访问 → cold
    store.add(
        "去年试用过某小众消息中间件",
        user_id="alice",
        retention=0.18,
        days_since_access=120,
    )
    # 另一条冷数据，用于回热实验
    store.add(
        "去年用 ECS + Docker 部署过 FastAPI",
        user_id="alice",
        retention=0.12,
        days_since_access=200,
    )
    return store


def demo_initial_tiers(store: TieredMemoryStore) -> None:
    print("=" * 64)
    print("实验 1：写入后按温度分流")
    print("=" * 64)

    counts = store.counts_by_tier()
    print(f"\n  分层统计：{counts}")
    for mem in list(store.memories.values()) + list(store.archive.values()):
        flag = "索引中" if mem.in_hot_index else "已出热索引"
        print(
            f"  - [{mem.id}] tier={mem.tier:<4} R={mem.retention:.2f} "
            f"idle={mem.days_since_access:>3}d ({flag}) {mem.content}"
        )

    assert counts["hot"] >= 2
    assert counts["warm"] >= 1
    assert counts["cold"] >= 2
    print("  → 正确：画像/高保留进热层，中期进温层，长期未访问进冷层")


def demo_hot_search_excludes_cold(store: TieredMemoryStore) -> None:
    print("\n" + "=" * 64)
    print("实验 2：日常检索不扫冷层")
    print("=" * 64)

    hot_hits = store.search("Docker 部署 FastAPI", user_id="alice", include_cold=False)
    cold_hits = store.search("Docker 部署 FastAPI", user_id="alice", include_cold=True)

    print("\n  [日常检索 include_cold=False]")
    if not hot_hits:
        print("  (无结果) → 冷层历史不会干扰日常 Prompt")
    else:
        for mem in hot_hits:
            print(f"  - [{mem.id}] {mem.tier} {mem.content}")

    print("\n  [追溯检索 include_cold=True]")
    for mem in cold_hits:
        print(f"  - [{mem.id}] {mem.tier} {mem.content}")

    assert not any("去年用 ECS" in mem.content for mem in hot_hits)
    assert any("去年用 ECS" in mem.content for mem in cold_hits)
    print("  → 正确：热层为延迟买单，冷层按需加载")


def demo_migrate_and_reheat(store: TieredMemoryStore) -> None:
    print("\n" + "=" * 64)
    print("实验 3：降温归档与回热唤醒")
    print("=" * 64)

    # 把一条温层记忆继续降温
    warm = next(mem for mem in store.memories.values() if mem.tier == "warm")
    print(f"\n  降温目标：[{warm.id}] {warm.content}")
    warm.retention = 0.2
    warm.days_since_access = 45
    moved = migrate_if_needed(store, warm)
    print(f"  migrate → {moved}")
    assert moved == "warm -> cold"
    assert warm.id in store.archive
    assert store.archive[warm.id].in_hot_index is False

    # 用户突然问起去年部署，回热那条冷记忆
    cold = next(mem for mem in store.archive.values() if "ECS" in mem.content)
    print(f"\n  回热目标：[{cold.id}] {cold.content}")
    cold.retention = 0.8
    cold.days_since_access = 0
    moved = migrate_if_needed(store, cold)
    print(f"  migrate → {moved}")
    assert moved == "cold -> hot"
    assert cold.id in store.memories
    assert store.memories[cold.id].in_hot_index is True

    reheated_hits = store.search("Docker 部署", user_id="alice")
    print("\n  回热后日常检索「Docker 部署」：")
    for mem in reheated_hits:
        print(f"  - [{mem.id}] {mem.tier} {mem.content}")
    assert any("ECS" in mem.content for mem in reheated_hits)
    print("  → 正确：降权管排序，分层管是否留在热检索面；可回热")


def print_summary(store: TieredMemoryStore) -> None:
    print("\n" + "=" * 64)
    print(f"当前分层快照：{store.counts_by_tier()}")
    print("总结")
    print("  1. assign_tier 用保留率 + 访问新鲜度决定 hot/warm/cold")
    print("  2. 冷数据必须移出热索引，不能只靠排序沉底")
    print("  3. 追溯场景再 include_cold / restore_to_hot")
    print("  4. 分层与艾宾浩斯降权配合，而不是互相替代")
    print("=" * 64)


def main() -> None:
    store = seed_store()
    demo_initial_tiers(store)
    demo_hot_search_excludes_cold(store)
    demo_migrate_and_reheat(store)
    print_summary(store)
    print("\n[PASS] d4_7_hot_cold_tier 全部断言通过")


if __name__ == "__main__":
    main()
