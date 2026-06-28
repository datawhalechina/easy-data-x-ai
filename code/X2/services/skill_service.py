"""
Skill service — CRUD operations delegated to SkillStorage.
"""

from typing import Optional, List

from models.skill import Skill
from storage.base import SkillStorage
from storage import create_storage


class SkillService:
    """Service for skill storage operations."""

    def __init__(self, storage_or_path: SkillStorage | str):
        if isinstance(storage_or_path, str):
            self.storage = create_storage(storage_or_path)
        else:
            self.storage = storage_or_path

    @classmethod
    def from_path(cls, db_path: str) -> "SkillService":
        return cls(create_storage(db_path))

    def create_skill(self, skill: Skill) -> str:
        return self.storage.create_skill(skill)

    def get_skill_by_name(self, name: str) -> Optional[Skill]:
        return self.storage.get_skill_by_name(name)

    def get_skill_by_id(self, skill_id: str) -> Optional[Skill]:
        # seekdb doc ids are skill:{name}; resolve via stored id on Skill objects
        for skill in self.storage.list_skills():
            if skill.id == skill_id:
                return skill
        return None

    def list_skills(
        self,
        category: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[Skill]:
        return self.storage.list_skills(category=category, status=status)

    def update_skill(self, skill: Skill) -> bool:
        return self.storage.update_skill(skill)

    def delete_skill(self, name: str) -> bool:
        return self.storage.delete_skill_by_name(name)
