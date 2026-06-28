"""
Rule data model.

Represents a rule extracted from skill content.
"""

from typing import Optional
from datetime import datetime


class Rule:
    """
    Rule data model.
    
    Represents a rule extracted from skill content.
    """
    
    def __init__(
        self,
        skill_name: str,
        rule_type: str,
        rule_key: str,
        rule_value: str,
        rule_description: Optional[str] = None,
        priority: int = 0,
        rule_id: Optional[str] = None,
        created_at: Optional[datetime] = None
    ):
        """
        Initialize a Rule instance.
        
        Args:
            skill_name: Name of the associated skill
            rule_type: Type of rule (syntax, naming, format, structure, style)
            rule_key: Rule key (unique within a skill)
            rule_value: Rule value or content
            rule_description: Optional rule description
            priority: Priority (higher number = higher priority)
            rule_id: Storage document id (None for new rules)
            created_at: Creation timestamp
        """
        self.id = rule_id
        self.skill_name = skill_name
        self.rule_type = rule_type
        self.rule_key = rule_key
        self.rule_value = rule_value
        self.rule_description = rule_description
        self.priority = priority
        self.created_at = created_at
    
    def to_dict(self) -> dict:
        """
        Convert rule to dictionary.
        
        Returns:
            Dictionary representation of the rule
        """
        return {
            'id': self.id,
            'skill_name': self.skill_name,
            'rule_type': self.rule_type,
            'rule_key': self.rule_key,
            'rule_value': self.rule_value,
            'rule_description': self.rule_description,
            'priority': self.priority,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Rule':
        """
        Create Rule instance from dictionary.
        
        Args:
            data: Dictionary containing rule data
            
        Returns:
            Rule instance
        """
        # Parse timestamp
        created_at = None
        if data.get('created_at'):
            if isinstance(data['created_at'], str):
                created_at = datetime.fromisoformat(data['created_at'])
            else:
                created_at = data['created_at']
        
        return cls(
            rule_id=data.get('id'),
            skill_name=data.get('skill_name') or data.get('skill_id', ''),
            rule_type=data['rule_type'],
            rule_key=data['rule_key'],
            rule_value=data['rule_value'],
            rule_description=data.get('rule_description'),
            priority=data.get('priority', 0),
            created_at=created_at
        )
    
    @classmethod
    def from_db_row(cls, row: tuple, columns: tuple) -> 'Rule':
        """
        Create Rule instance from database row.
        
        Args:
            row: Database row tuple
            columns: Column names tuple
            
        Returns:
            Rule instance
        """
        data = dict(zip(columns, row))
        return cls.from_dict(data)
    
    def __repr__(self) -> str:
        return f"Rule(id={self.id}, skill_name={self.skill_name!r}, type='{self.rule_type}', key='{self.rule_key}')"
