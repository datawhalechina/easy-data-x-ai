"""
Markdown parser for SKILL.md files.

Parses SKILL.md files and extracts frontmatter (YAML) and content.
"""

import re
import yaml
from pathlib import Path
from typing import Dict, Any, Optional


class MarkdownParser:
    """
    Parser for SKILL.md files.
    
    Extracts frontmatter (YAML) and content from Markdown files.
    """
    
    def __init__(self, file_path: str):
        """
        Initialize parser with file path.
        
        Args:
            file_path: Path to SKILL.md file
        """
        self.file_path = Path(file_path)
        if not self.file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
    
    def parse(self) -> Dict[str, Any]:
        """
        Parse the Markdown file and extract frontmatter and content.
        
        Returns:
            Dictionary containing:
            - name: Skill name (from frontmatter)
            - description: Skill description (from frontmatter)
            - content: Full Markdown content (without frontmatter)
            - frontmatter: Complete frontmatter dictionary
            - category: Extracted category (from name or frontmatter)
        """
        with open(self.file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Extract frontmatter (YAML between --- markers)
        frontmatter_match = re.match(
            r'^---\s*\n(.*?)\n---\s*\n',
            content,
            re.DOTALL
        )
        
        if frontmatter_match:
            frontmatter_str = frontmatter_match.group(1)
            frontmatter = yaml.safe_load(frontmatter_str) or {}
            body_content = content[frontmatter_match.end():]
        else:
            frontmatter = {}
            body_content = content
        
        # Extract basic information
        name = frontmatter.get('name', '')
        description = frontmatter.get('description', '')
        
        category = self._extract_category(name, frontmatter)
        
        return {
            'name': name,
            'description': description,
            'content': body_content.strip(),
            'frontmatter': frontmatter,
            'category': category,
            'version': frontmatter.get('version', '1.0.0'),
            'license': frontmatter.get('license'),
            'compatibility': frontmatter.get('compatibility'),
            'metadata': frontmatter.get('metadata', {})
        }
    
    def _extract_category(self, name: str, frontmatter: Dict[str, Any]) -> Optional[str]:
        """
        Extract category from skill name or frontmatter.
        
        Args:
            name: Skill name
            frontmatter: Frontmatter dictionary
            
        Returns:
            Category string or None
        """
        # Try to get from frontmatter first
        if 'category' in frontmatter:
            return frontmatter['category']
        
        # Infer from name segments: e.g. 'api-doc-writing' -> 'doc-writing'
        parts = name.split('-')
        if len(parts) > 1:
            return '-'.join(parts[1:])
        return parts[0] if parts else None
