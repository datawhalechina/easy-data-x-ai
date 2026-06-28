"""
Query service — read and search operations delegated to SkillStorage.
"""

from typing import Optional, List, Dict, Any

from models.skill import Skill
from models.rule import Rule
from models.example import Example
from storage.base import SkillStorage
from storage import create_storage


class QueryService:
    """Service for querying skills, rules, and examples."""

    def __init__(self, storage_or_path: SkillStorage | str):
        if isinstance(storage_or_path, str):
            self.storage = create_storage(storage_or_path)
        else:
            self.storage = storage_or_path

    @classmethod
    def from_path(cls, db_path: str) -> "QueryService":
        return cls(create_storage(db_path))

    def get_skill_complete(self, skill_name: str) -> Optional[Dict[str, Any]]:
        skill = self.storage.get_skill_by_name(skill_name)
        if not skill:
            return None

        rules = self.storage.get_rules_by_skill(skill_name)
        examples = self.storage.get_examples_by_skill(skill_name)

        skill_data = skill.to_dict()
        return {
            "skill": skill_data,
            "rules": [r.to_dict() for r in rules],
            "examples": [e.to_dict() for e in examples],
            "rule_count": len(rules),
            "example_count": len(examples),
        }

    def get_rules_by_skill(self, skill_name: str) -> List[Rule]:
        return self.storage.get_rules_by_skill(skill_name)

    def get_examples_by_skill(self, skill_name: str) -> List[Example]:
        return self.storage.get_examples_by_skill(skill_name)

    def search_skills(self, keyword: str, n_results: int = 5) -> List[Skill]:
        return self.storage.search_skills(keyword, n_results=n_results)

    def get_skills_by_category(self, category: str) -> List[Skill]:
        return self.storage.list_skills(category=category)
