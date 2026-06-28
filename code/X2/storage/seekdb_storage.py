"""seekdb implementation of SkillStorage."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import pyseekdb

from database.seekdb_client import create_client
from database.collections import (
    DEFAULT_SEEKDB_PATH,
    EXAMPLES_COLLECTION,
    RULES_COLLECTION,
    SKILLS_COLLECTION,
    example_doc_id,
    rule_doc_id,
    skill_doc_id,
)
from models.example import Example
from models.rule import Rule
from models.skill import Skill
from storage.base import SkillStorage


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_metadata(raw: Any) -> dict:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw:
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {}
    return {}


class SeekdbStorage(SkillStorage):
    """Store skills / rules / examples in three seekdb collections."""

    def __init__(self, path: str = DEFAULT_SEEKDB_PATH):
        self.path = path
        self._client: pyseekdb.Client | None = None
        self._skills_col = None
        self._rules_col = None
        self._examples_col = None

    @property
    def client(self) -> pyseekdb.Client:
        if self._client is None:
            self._client = create_client(self.path)
        return self._client

    def _bind_collections(self) -> None:
        self._skills_col = self.client.get_or_create_collection(SKILLS_COLLECTION)
        self._rules_col = self.client.get_or_create_collection(RULES_COLLECTION)
        self._examples_col = self.client.get_or_create_collection(EXAMPLES_COLLECTION)

    def init(self, force: bool = False) -> None:
        if force:
            for name in (SKILLS_COLLECTION, RULES_COLLECTION, EXAMPLES_COLLECTION):
                if self.client.has_collection(name):
                    self.client.delete_collection(name)
        self._bind_collections()

    def is_initialized(self) -> bool:
        return (
            self.client.has_collection(SKILLS_COLLECTION)
            and self.client.has_collection(RULES_COLLECTION)
            and self.client.has_collection(EXAMPLES_COLLECTION)
        )

    def _ensure_collections(self) -> None:
        if not self.is_initialized():
            self.init(force=False)
        elif self._skills_col is None:
            self._bind_collections()

    # --- skill metadata helpers ---

    def _skill_to_metadata(self, skill: Skill, created_at: str | None = None) -> dict:
        meta = {
            "name": skill.name,
            "description": skill.description,
            "content": skill.content,
            "category": skill.category or "",
            "version": skill.version or "1.0.0",
            "license": skill.license or "",
            "compatibility": skill.compatibility or "",
            "metadata_json": skill.get_metadata_json(),
            "status": skill.status or "active",
            "created_at": created_at or _utc_now_iso(),
            "updated_at": _utc_now_iso(),
        }
        return meta

    def _metadata_to_skill(self, meta: dict, doc_id: str) -> Skill:
        return Skill(
            skill_id=doc_id,
            name=meta["name"],
            description=meta["description"],
            content=meta.get("content", ""),
            category=meta.get("category") or None,
            version=meta.get("version", "1.0.0"),
            license=meta.get("license") or None,
            compatibility=meta.get("compatibility") or None,
            metadata=_parse_metadata(meta.get("metadata_json", "{}")),
            status=meta.get("status", "active"),
            created_at=_parse_ts(meta.get("created_at")),
            updated_at=_parse_ts(meta.get("updated_at")),
        )

    def _skill_search_document(self, skill: Skill) -> str:
        parts = [skill.name, skill.description]
        if skill.category:
            parts.append(skill.category)
        return "\n".join(p for p in parts if p)

    # --- skills CRUD ---

    def create_skill(self, skill: Skill) -> str:
        self._ensure_collections()
        doc_id = skill_doc_id(skill.name)
        existing = self._skills_col.get(ids=[doc_id])
        if existing.get("ids"):
            raise ValueError(f"Skill with name '{skill.name}' already exists")

        self._skills_col.upsert(
            ids=[doc_id],
            documents=[self._skill_search_document(skill)],
            metadatas=[self._skill_to_metadata(skill)],
        )
        return doc_id

    def get_skill_by_name(self, name: str) -> Skill | None:
        self._ensure_collections()
        result = self._skills_col.get(ids=[skill_doc_id(name)])
        if not result.get("ids"):
            return None
        return self._metadata_to_skill(result["metadatas"][0], result["ids"][0])

    def list_skills(
        self,
        category: str | None = None,
        status: str | None = None,
    ) -> list[Skill]:
        self._ensure_collections()
        where: dict[str, Any] = {}
        if category:
            where["category"] = category
        if status:
            where["status"] = status

        if where:
            result = self._skills_col.get(where=where)
        else:
            result = self._skills_col.get()

        skills = []
        for doc_id, meta in zip(result.get("ids", []), result.get("metadatas", [])):
            skills.append(self._metadata_to_skill(meta, doc_id))
        return sorted(skills, key=lambda s: s.name)

    def update_skill(self, skill: Skill) -> bool:
        self._ensure_collections()
        doc_id = skill_doc_id(skill.name)
        existing = self._skills_col.get(ids=[doc_id])
        if not existing.get("ids"):
            return False

        created_at = existing["metadatas"][0].get("created_at")
        self._skills_col.upsert(
            ids=[doc_id],
            documents=[self._skill_search_document(skill)],
            metadatas=[self._skill_to_metadata(skill, created_at=created_at)],
        )
        return True

    def delete_skill_by_name(self, name: str) -> bool:
        self._ensure_collections()
        doc_id = skill_doc_id(name)
        existing = self._skills_col.get(ids=[doc_id])
        if not existing.get("ids"):
            return False

        self.delete_rules_by_skill(name)
        self.delete_examples_by_skill(name)
        self._skills_col.delete(ids=[doc_id])
        return True

    # --- rules ---

    def insert_rules(self, rules: list[Rule]) -> int:
        if not rules:
            return 0
        self._ensure_collections()

        ids, documents, metadatas = [], [], []
        for rule in rules:
            ids.append(rule_doc_id(rule.skill_name, rule.rule_key))
            documents.append(rule.rule_value)
            metadatas.append({
                "skill_name": rule.skill_name,
                "rule_type": rule.rule_type,
                "rule_key": rule.rule_key,
                "rule_description": rule.rule_description or "",
                "priority": rule.priority,
                "created_at": _utc_now_iso(),
            })

        self._rules_col.upsert(ids=ids, documents=documents, metadatas=metadatas)
        return len(ids)

    def get_rules_by_skill(self, skill_name: str) -> list[Rule]:
        self._ensure_collections()
        result = self._rules_col.get(where={"skill_name": skill_name})
        rules = []
        for doc_id, meta, doc in zip(
            result.get("ids", []),
            result.get("metadatas", []),
            result.get("documents", []),
        ):
            rules.append(self._metadata_to_rule(meta, doc_id, doc))
        return sorted(rules, key=lambda r: (-r.priority, r.rule_key))

    def delete_rules_by_skill(self, skill_name: str) -> int:
        self._ensure_collections()
        result = self._rules_col.get(where={"skill_name": skill_name})
        ids = result.get("ids", [])
        if ids:
            self._rules_col.delete(ids=ids)
        return len(ids)

    # --- examples ---

    def insert_examples(self, examples: list[Example]) -> int:
        if not examples:
            return 0
        self._ensure_collections()

        ids, documents, metadatas = [], [], []
        for ex in examples:
            ids.append(example_doc_id(ex.skill_name, ex.order_index))
            documents.append(ex.code)
            metadatas.append({
                "skill_name": ex.skill_name,
                "example_type": ex.example_type or "text",
                "title": ex.title or "",
                "result": ex.result or "",
                "description": ex.description or "",
                "order_index": ex.order_index,
                "created_at": _utc_now_iso(),
            })

        self._examples_col.upsert(ids=ids, documents=documents, metadatas=metadatas)
        return len(ids)

    def get_examples_by_skill(self, skill_name: str) -> list[Example]:
        self._ensure_collections()
        result = self._examples_col.get(where={"skill_name": skill_name})
        examples = []
        for doc_id, meta, doc in zip(
            result.get("ids", []),
            result.get("metadatas", []),
            result.get("documents", []),
        ):
            examples.append(self._metadata_to_example(meta, doc_id, doc))
        return sorted(examples, key=lambda e: e.order_index)

    def delete_examples_by_skill(self, skill_name: str) -> int:
        self._ensure_collections()
        result = self._examples_col.get(where={"skill_name": skill_name})
        ids = result.get("ids", [])
        if ids:
            self._examples_col.delete(ids=ids)
        return len(ids)

    # --- search ---

    def search_skills(self, query: str, n_results: int = 5) -> list[Skill]:
        """Hybrid search: vector + full-text via seekdb query()."""
        self._ensure_collections()
        if not query.strip():
            return self.list_skills()

        kwargs: dict[str, Any] = {
            "query_texts": [query],
            "n_results": n_results,
        }
        # Full-text leg when query has usable tokens
        if len(query.strip()) >= 2:
            kwargs["where_document"] = {"$contains": query}

        try:
            result = self._skills_col.query(**kwargs)
        except Exception:
            # Fallback: metadata filter on name/description not available — list all
            return [
                s for s in self.list_skills()
                if query.lower() in s.name.lower() or query.lower() in s.description.lower()
            ][:n_results]

        skills = []
        for doc_id, meta in zip(result.get("ids", [[]])[0], result.get("metadatas", [[]])[0]):
            skills.append(self._metadata_to_skill(meta, doc_id))
        return skills

    def get_migration_summary(self) -> dict[str, Any]:
        self._ensure_collections()
        skills = self._skills_col.get()
        rules = self._rules_col.get()
        examples = self._examples_col.get()

        category_counts: dict[str, int] = {}
        for meta in skills.get("metadatas", []):
            cat = meta.get("category") or "uncategorized"
            category_counts[cat] = category_counts.get(cat, 0) + 1

        return {
            "skill_count": len(skills.get("ids", [])),
            "rule_count": len(rules.get("ids", [])),
            "example_count": len(examples.get("ids", [])),
            "category_counts": category_counts,
        }

    # --- converters ---

    def _metadata_to_rule(self, meta: dict, doc_id: str, document: str) -> Rule:
        return Rule(
            rule_id=doc_id,
            skill_name=meta["skill_name"],
            rule_type=meta["rule_type"],
            rule_key=meta["rule_key"],
            rule_value=document,
            rule_description=meta.get("rule_description") or None,
            priority=int(meta.get("priority", 0)),
            created_at=_parse_ts(meta.get("created_at")),
        )

    def _metadata_to_example(self, meta: dict, doc_id: str, document: str) -> Example:
        return Example(
            example_id=doc_id,
            skill_name=meta["skill_name"],
            example_type=meta.get("example_type") or None,
            title=meta.get("title") or None,
            code=document,
            result=meta.get("result") or None,
            description=meta.get("description") or None,
            order_index=int(meta.get("order_index", 0)),
            created_at=_parse_ts(meta.get("created_at")),
        )


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None
