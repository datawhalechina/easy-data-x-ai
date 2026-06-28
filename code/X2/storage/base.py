"""Abstract storage interface for Skill / Rule / Example persistence."""

from abc import ABC, abstractmethod
from typing import Any

from models.skill import Skill
from models.rule import Rule
from models.example import Example


class SkillStorage(ABC):
    """Backend-agnostic storage for skills, rules, and examples."""

    @abstractmethod
    def init(self, force: bool = False) -> None:
        """Initialize or reset storage collections."""

    @abstractmethod
    def is_initialized(self) -> bool:
        """Return True if storage has been initialized."""

    # --- skills ---

    @abstractmethod
    def create_skill(self, skill: Skill) -> str:
        """Persist a new skill. Returns document id."""

    @abstractmethod
    def get_skill_by_name(self, name: str) -> Skill | None:
        ...

    @abstractmethod
    def list_skills(
        self,
        category: str | None = None,
        status: str | None = None,
    ) -> list[Skill]:
        ...

    @abstractmethod
    def update_skill(self, skill: Skill) -> bool:
        ...

    @abstractmethod
    def delete_skill_by_name(self, name: str) -> bool:
        """Delete skill and all related rules/examples."""

    # --- rules ---

    @abstractmethod
    def insert_rules(self, rules: list[Rule]) -> int:
        ...

    @abstractmethod
    def get_rules_by_skill(self, skill_name: str) -> list[Rule]:
        ...

    @abstractmethod
    def delete_rules_by_skill(self, skill_name: str) -> int:
        ...

    # --- examples ---

    @abstractmethod
    def insert_examples(self, examples: list[Example]) -> int:
        ...

    @abstractmethod
    def get_examples_by_skill(self, skill_name: str) -> list[Example]:
        ...

    @abstractmethod
    def delete_examples_by_skill(self, skill_name: str) -> int:
        ...

    # --- search ---

    @abstractmethod
    def search_skills(self, query: str, n_results: int = 5) -> list[Skill]:
        ...

    @abstractmethod
    def get_migration_summary(self) -> dict[str, Any]:
        ...
