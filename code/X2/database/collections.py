"""seekdb collection names and document ID helpers for X2 Skill storage."""

SKILLS_COLLECTION = "x2_skills"
RULES_COLLECTION = "x2_rules"
EXAMPLES_COLLECTION = "x2_examples"

DEFAULT_SEEKDB_PATH = "database/skills.seekdb"


def skill_doc_id(name: str) -> str:
    return f"skill:{name}"


def rule_doc_id(skill_name: str, rule_key: str) -> str:
    return f"skill:{skill_name}:rule:{rule_key}"


def example_doc_id(skill_name: str, order_index: int) -> str:
    return f"skill:{skill_name}:example:{order_index}"
