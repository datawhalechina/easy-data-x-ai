"""
Skill data model.

Represents a skill in the database with its metadata and content.
"""

from typing import Optional, Dict, Any
from datetime import datetime
import json


class Skill:
    """
    Skill data model.
    
    Represents a skill with its basic information and full content.
    """
    
    def __init__(
        self,
        name: str,
        description: str,
        content: str,
        category: Optional[str] = None,
        version: str = '1.0.0',
        license: Optional[str] = None,
        compatibility: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        status: str = 'active',
        skill_id: Optional[str] = None,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None
    ):
        """
        Initialize a Skill instance.
        
        Args:
            name: Skill name (unique identifier)
            description: Skill description
            content: Full skill content (Markdown)
            category: Skill category (sql-doc, formatting, examples, syntax)
            version: Version number
            license: License (e.g., MIT)
            compatibility: Compatibility information (e.g., opencode)
            metadata: Extended metadata as dictionary
            status: Status (active, deprecated, draft)
            skill_id: Database ID (None for new skills)
            created_at: Creation timestamp
            updated_at: Last update timestamp
        """
        self.id = skill_id
        self.name = name
        self.description = description
        self.content = content
        self.category = category
        self.version = version
        self.license = license
        self.compatibility = compatibility
        self.metadata = metadata or {}
        self.status = status
        self.created_at = created_at
        self.updated_at = updated_at
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert skill to dictionary.
        
        Returns:
            Dictionary representation of the skill
        """
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'content': self.content,
            'category': self.category,
            'version': self.version,
            'license': self.license,
            'compatibility': self.compatibility,
            'metadata': self.metadata,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Skill':
        """
        Create Skill instance from dictionary.
        
        Args:
            data: Dictionary containing skill data
            
        Returns:
            Skill instance
        """
        # Parse timestamps
        created_at = None
        updated_at = None
        if data.get('created_at'):
            if isinstance(data['created_at'], str):
                created_at = datetime.fromisoformat(data['created_at'])
            else:
                created_at = data['created_at']
        if data.get('updated_at'):
            if isinstance(data['updated_at'], str):
                updated_at = datetime.fromisoformat(data['updated_at'])
            else:
                updated_at = data['updated_at']
        
        # Parse metadata if it's a JSON string
        metadata = data.get('metadata')
        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except json.JSONDecodeError:
                metadata = {}
        elif metadata is None:
            metadata = {}
        
        return cls(
            skill_id=data.get('id'),
            name=data['name'],
            description=data['description'],
            content=data['content'],
            category=data.get('category'),
            version=data.get('version', '1.0.0'),
            license=data.get('license'),
            compatibility=data.get('compatibility'),
            metadata=metadata,
            status=data.get('status', 'active'),
            created_at=created_at,
            updated_at=updated_at
        )
    
    @classmethod
    def from_db_row(cls, row: tuple, columns: tuple) -> 'Skill':
        """
        Create Skill instance from database row.
        
        Args:
            row: Database row tuple
            columns: Column names tuple
            
        Returns:
            Skill instance
        """
        data = dict(zip(columns, row))
        return cls.from_dict(data)
    
    def get_metadata_json(self) -> str:
        """
        Get metadata as JSON string.
        
        Returns:
            JSON string representation of metadata
        """
        return json.dumps(self.metadata) if self.metadata else '{}'
    
    def __repr__(self) -> str:
        return f"Skill(id={self.id}, name='{self.name}', category='{self.category}', status='{self.status}')"
