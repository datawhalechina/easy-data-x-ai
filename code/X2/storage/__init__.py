"""Storage backends for X2 Skill management."""

from .base import SkillStorage
from .seekdb_storage import SeekdbStorage

__all__ = ["SkillStorage", "SeekdbStorage", "create_storage"]


def create_storage(path: str | None = None) -> SkillStorage:
    """Create the default seekdb-backed storage."""
    from database.collections import DEFAULT_SEEKDB_PATH

    return SeekdbStorage(path or DEFAULT_SEEKDB_PATH)
