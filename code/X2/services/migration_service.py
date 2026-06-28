"""
Migration service — migrate SKILL.md files into seekdb storage.
"""

from typing import List, Dict, Any
from pathlib import Path

from parsers import MarkdownParser, RuleExtractor, ExampleExtractor
from models.skill import Skill
from storage.base import SkillStorage
from storage import create_storage


class MigrationService:
    """Migrate Skills from Markdown files to storage."""

    def __init__(self, storage_or_path: SkillStorage | str):
        if isinstance(storage_or_path, str):
            self.storage = create_storage(storage_or_path)
        else:
            self.storage = storage_or_path

    @classmethod
    def from_path(cls, db_path: str) -> "MigrationService":
        return cls(create_storage(db_path))

    def migrate_skill_file(self, skill_file_path: str, force: bool = False) -> Dict[str, Any]:
        skill_file = Path(skill_file_path)
        if not skill_file.exists():
            raise FileNotFoundError(f"Skill file not found: {skill_file_path}")

        parser = MarkdownParser(str(skill_file))
        data = parser.parse()
        skill_name = data["name"]

        existing = self.storage.get_skill_by_name(skill_name)
        if existing and not force:
            return {
                "status": "skipped",
                "skill_name": skill_name,
                "message": f"Skill '{skill_name}' already exists. Use force=True to update.",
            }

        skill = Skill(
            name=skill_name,
            description=data["description"],
            content=data["content"],
            category=data["category"],
            version=data["version"],
            license=data["license"],
            compatibility=data["compatibility"],
            metadata=data["metadata"],
            status="active",
        )

        if existing and force:
            self.storage.delete_rules_by_skill(skill_name)
            self.storage.delete_examples_by_skill(skill_name)
            self.storage.update_skill(skill)
            doc_id = existing.id
            action = "updated"
        else:
            doc_id = self.storage.create_skill(skill)
            action = "created"

        rules = RuleExtractor(data["content"]).extract(skill_name)
        examples = ExampleExtractor(data["content"]).extract(skill_name)
        rule_count = self.storage.insert_rules(rules)
        example_count = self.storage.insert_examples(examples)

        return {
            "status": "success",
            "skill_name": skill_name,
            "skill_id": doc_id,
            "rule_count": rule_count,
            "example_count": example_count,
            "action": action,
        }

    def migrate_directory(self, skills_dir: str, force: bool = False) -> List[Dict[str, Any]]:
        skills_dir_path = Path(skills_dir)
        if not skills_dir_path.exists():
            raise FileNotFoundError(f"Directory not found: {skills_dir}")

        results = []
        for skill_file in skills_dir_path.glob("*/SKILL.md"):
            try:
                results.append(self.migrate_skill_file(str(skill_file), force=force))
            except Exception as e:
                results.append({
                    "status": "error",
                    "skill_file": str(skill_file),
                    "error": str(e),
                })
        return results

    def get_migration_summary(self) -> Dict[str, Any]:
        return self.storage.get_migration_summary()
