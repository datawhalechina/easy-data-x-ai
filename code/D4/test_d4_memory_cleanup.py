import unittest
from copy import deepcopy
from datetime import datetime, timedelta

from d4_8_memory_cleanup import LifecycleMemoryStore, cleanup_memories


class CleanupLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.start = datetime(2026, 1, 1, 12, 0, 0)
        self.store = LifecycleMemoryStore()

    def clean(self, day, *, user_id="alice", dry_run=False):
        return cleanup_memories(
            self.store,
            self.start + timedelta(days=day),
            user_id=user_id,
            dry_run=dry_run,
        )

    def test_archived_memory_is_deleted_when_it_later_expires(self):
        memory = self.store.add("临时事实", "alice", created_at=self.start)

        self.assertEqual(self.clean(30)["archived"], 1)
        self.assertIn(memory.id, self.store.archive)
        self.assertNotIn(memory.id, self.store.vector_index)
        self.assertNotIn(memory.id, self.store.cache)

        # 已归档记忆不重复归档，也不能在满 90 天前硬删。
        self.assertEqual(self.clean(89)["actions"], [])
        self.assertIn(memory.id, self.store.records)
        self.assertEqual(self.clean(90)["deleted"], 1)
        for collection in (
            self.store.records, self.store.archive,
            self.store.vector_index, self.store.cache,
        ):
            self.assertNotIn(memory.id, collection)
        self.assertEqual(self.clean(100)["actions"], [])

    def test_dry_run_reports_expired_archive_without_mutating_store(self):
        memory = self.store.add("临时事实", "alice", created_at=self.start)
        self.clean(30)
        before = deepcopy(self.store)

        preview = self.clean(100, dry_run=True)

        self.assertEqual(preview["deleted"], 1)
        self.assertEqual(self.store, before)
        self.assertEqual(self.clean(100), preview)
        self.assertNotIn(memory.id, self.store.records)
        self.assertNotIn(memory.id, self.store.archive)

    def test_protected_archive_is_retained_on_later_cleanup(self):
        memory = self.store.add(
            "primary_language=Python", "alice",
            created_at=self.start, protected=True,
        )
        self.assertEqual(self.clean(30)["archived"], 1)
        before = deepcopy(self.store)

        result = self.clean(120)

        self.assertEqual(result["deleted"], 0)
        self.assertEqual(result["actions"], [])
        self.assertEqual(self.store, before)
        self.assertIn(memory.id, self.store.archive)

    def test_archived_memory_with_sufficient_retention_is_not_deleted(self):
        memory = self.store.add(
            "经常用到的事实", "alice", created_at=self.start, access_count=3,
        )
        self.clean(30)
        before = deepcopy(self.store)

        self.assertEqual(self.clean(120)["actions"], [])
        self.assertEqual(self.store, before)
        self.assertIn(memory.id, self.store.archive)

    def test_expired_archives_are_deleted_only_for_the_requested_user(self):
        alice = self.store.add("Alice 的事实", "alice", created_at=self.start)
        bob = self.store.add("Bob 的事实", "bob", created_at=self.start)
        self.clean(30, user_id="alice")
        self.clean(30, user_id="bob")
        bob_before = deepcopy(self.store.records[bob.id])

        self.assertEqual(self.clean(100, user_id="alice")["deleted"], 1)
        self.assertNotIn(alice.id, self.store.records)
        self.assertNotIn(alice.id, self.store.archive)
        self.assertEqual(self.store.records[bob.id], bob_before)
        self.assertEqual(self.store.archive[bob.id], bob_before)


if __name__ == "__main__":
    unittest.main()
