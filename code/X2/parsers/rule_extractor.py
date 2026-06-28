"""
Rule extractor from Markdown content.

Extracts rules from Markdown content based on section headers and list items.
"""

import re
from typing import List, Dict, Any
from models.rule import Rule


class RuleExtractor:
    """
    Extracts rules from Markdown content.
    
    Identifies rule sections and extracts rules as list items or key descriptions.
    """
    
    # Rule section patterns (case-insensitive)
    RULE_SECTION_PATTERNS = [
        r'##\s+Formatting\s+rules',
        r'##\s+Syntax\s+section\s+rules',
        r'##\s+Naming\s+conventions?',  # Added: ## Naming conventions
        r'##\s+Syntax\s+notation',  # Added: ## Syntax notation
        r'##\s+Common\s+patterns?',  # Added: ## Common patterns
        r'##\s+Best\s+practices?',  # Added: ## Best practices
        r'###\s+Syntax\s+section',
        r'###\s+Examples?\s+section',
        r'###\s+Naming\s+conventions?',
        r'###\s+Spacing\s+rules',
        r'##\s+Markdown\s+lint\s+compliance',
        r'##\s+.*[Rr]ules?',  # Any section with "rules" in title
    ]
    
    # Rule type mapping based on section keywords
    RULE_TYPE_MAPPING = {
        'syntax': 'syntax',
        'naming': 'naming',
        'spacing': 'format',
        'formatting': 'format',
        'format': 'format',
        'example': 'format',
        'structure': 'structure',
        'style': 'style',
        'lint': 'format',
        'compliance': 'format',
    }
    
    def __init__(self, content: str):
        """
        Initialize extractor with Markdown content.
        
        Args:
            content: Markdown content string
        """
        self.content = content
    
    def extract(self, skill_name: str) -> List[Rule]:
        """
        Extract rules from Markdown content.
        
        Args:
            skill_name: Name of the associated skill
            
        Returns:
            List of Rule objects
        """
        rules = []
        
        # Find all rule sections
        rule_sections = self._find_rule_sections()
        
        for section in rule_sections:
            section_title = section['title']
            section_content = section['content']
            rule_type = self._determine_rule_type(section_title)
            
            # Extract list items from section
            list_items = self._extract_list_items(section_content)
            
            for item in list_items:
                rule_key = self._generate_rule_key(item, rule_type)
                priority = self._determine_priority(item, rule_type)
                
                rule = Rule(
                    skill_name=skill_name,
                    rule_type=rule_type,
                    rule_key=rule_key,
                    rule_value=item,
                    priority=priority
                )
                rules.append(rule)
        
        return rules
    
    def _find_rule_sections(self) -> List[Dict[str, str]]:
        """
        Find all rule sections in the content.
        
        Returns:
            List of dictionaries with 'title' and 'content' keys
        """
        sections = []
        lines = self.content.split('\n')
        
        i = 0
        while i < len(lines):
            line = lines[i]
            
            # Check if line matches a rule section pattern
            for pattern in self.RULE_SECTION_PATTERNS:
                if re.match(pattern, line, re.IGNORECASE):
                    # Found a rule section, extract its content
                    section_title = line.strip()
                    section_content = []
                    
                    # Collect content until next major section (##)
                    # Include sub-sections (###) within this section
                    i += 1
                    while i < len(lines):
                        next_line = lines[i]
                        # Stop at next major section (##), but continue for sub-sections (###)
                        if re.match(r'^##\s+', next_line) and not re.match(r'^###\s+', next_line):
                            break
                        section_content.append(next_line)
                        i += 1
                    
                    sections.append({
                        'title': section_title,
                        'content': '\n'.join(section_content)
                    })
                    break
            
            i += 1
        
        return sections
    
    def _determine_rule_type(self, section_title: str) -> str:
        """
        Determine rule type from section title.
        
        Args:
            section_title: Section title (e.g., "### Syntax section")
            
        Returns:
            Rule type (syntax, naming, format, structure, style)
        """
        title_lower = section_title.lower()
        
        # Check mapping
        for keyword, rule_type in self.RULE_TYPE_MAPPING.items():
            if keyword in title_lower:
                return rule_type
        
        # Default to 'format' if no match
        return 'format'
    
    def _extract_list_items(self, content: str) -> List[str]:
        """
        Extract list items from content.
        
        Args:
            content: Section content
            
        Returns:
            List of rule text strings
        """
        rules = []
        lines = content.split('\n')
        
        for line in lines:
            line = line.strip()
            
            # Match list items starting with - or *
            # Format: "- Rule text" or "- **Bold text**: Description"
            if re.match(r'^[-*]\s+', line):
                # Remove list marker and clean up
                rule_text = re.sub(r'^[-*]\s+', '', line)
                # Remove markdown formatting but keep text
                rule_text = re.sub(r'\*\*([^*]+)\*\*', r'\1', rule_text)  # Remove **bold**
                rule_text = re.sub(r'`([^`]+)`', r'\1', rule_text)  # Remove `code`
                rule_text = rule_text.strip()
                
                if rule_text and len(rule_text) > 5:  # Filter out very short items
                    rules.append(rule_text)
        
        return rules
    
    def _generate_rule_key(self, rule_text: str, rule_type: str) -> str:
        """
        Generate a rule key from rule text.
        
        Args:
            rule_text: Rule text
            rule_type: Rule type
            
        Returns:
            Rule key (e.g., "no_semicolon_in_syntax")
        """
        # Convert to lowercase
        key = rule_text.lower()
        
        # Remove special characters, keep alphanumeric and spaces
        key = re.sub(r'[^a-z0-9\s]', '', key)
        
        # Replace spaces with underscores
        key = re.sub(r'\s+', '_', key)
        
        # Remove leading/trailing underscores
        key = key.strip('_')
        
        # Limit length
        if len(key) > 100:
            key = key[:100]
        
        # If key is too short or empty, use a default
        if len(key) < 3:
            key = f"{rule_type}_rule"
        
        return key
    
    def _determine_priority(self, rule_text: str, rule_type: str) -> int:
        """
        Determine priority for a rule.
        
        Args:
            rule_text: Rule text
            rule_type: Rule type
            
        Returns:
            Priority (higher number = higher priority)
        """
        priority = 0
        
        # Higher priority for syntax rules
        if rule_type == 'syntax':
            priority = 10
        elif rule_type == 'naming':
            priority = 8
        elif rule_type == 'format':
            priority = 5
        else:
            priority = 3
        
        # Boost priority for rules with "must", "should", "always"
        if any(word in rule_text.lower() for word in ['must', 'always', 'required']):
            priority += 5
        elif any(word in rule_text.lower() for word in ['should', 'recommended']):
            priority += 2
        
        # Boost priority for rules with "NOT" or "do not"
        if any(phrase in rule_text.lower() for phrase in ['not', 'do not', 'never']):
            priority += 3
        
        return priority
