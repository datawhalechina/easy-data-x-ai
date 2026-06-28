"""
Example data model.

Represents a code example with optional execution results.
"""

from typing import Optional
from datetime import datetime


class Example:
    """
    Example data model.
    
    Represents a code example with optional execution results.
    """
    
    def __init__(
        self,
        skill_name: str,
        code: str,
        example_type: Optional[str] = None,
        title: Optional[str] = None,
        result: Optional[str] = None,
        description: Optional[str] = None,
        order_index: int = 0,
        example_id: Optional[str] = None,
        created_at: Optional[datetime] = None
    ):
        """
        Initialize an Example instance.
        
        Args:
            skill_name: Name of the associated skill
            code: Example code
            example_type: Type of example (sql, markdown, code, text)
            title: Optional example title
            result: Optional execution result
            description: Optional example description
            order_index: Sort order (higher number = appears later)
            example_id: Storage document id (None for new examples)
            created_at: Creation timestamp
        """
        self.id = example_id
        self.skill_name = skill_name
        self.example_type = example_type
        self.title = title
        self.code = code
        self.result = result
        self.description = description
        self.order_index = order_index
        self.created_at = created_at
    
    def to_dict(self) -> dict:
        """
        Convert example to dictionary.
        
        Returns:
            Dictionary representation of the example
        """
        return {
            'id': self.id,
            'skill_name': self.skill_name,
            'example_type': self.example_type,
            'title': self.title,
            'code': self.code,
            'result': self.result,
            'description': self.description,
            'order_index': self.order_index,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Example':
        """
        Create Example instance from dictionary.
        
        Args:
            data: Dictionary containing example data
            
        Returns:
            Example instance
        """
        # Parse timestamp
        created_at = None
        if data.get('created_at'):
            if isinstance(data['created_at'], str):
                created_at = datetime.fromisoformat(data['created_at'])
            else:
                created_at = data['created_at']
        
        return cls(
            example_id=data.get('id'),
            skill_name=data.get('skill_name') or str(data.get('skill_id', '')),
            example_type=data.get('example_type'),
            title=data.get('title'),
            code=data['code'],
            result=data.get('result'),
            description=data.get('description'),
            order_index=data.get('order_index', 0),
            created_at=created_at
        )
    
    @classmethod
    def from_db_row(cls, row: tuple, columns: tuple) -> 'Example':
        """
        Create Example instance from database row.
        
        Args:
            row: Database row tuple
            columns: Column names tuple
            
        Returns:
            Example instance
        """
        data = dict(zip(columns, row))
        return cls.from_dict(data)
    
    def __repr__(self) -> str:
        return f"Example(id={self.id}, skill_name={self.skill_name!r}, type='{self.example_type}', order={self.order_index})"
