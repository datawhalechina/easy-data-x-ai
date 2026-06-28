"""
Example extractor from Markdown content.

Extracts code examples from Markdown content, including code blocks and results.
"""

import re
from typing import List, Optional, Tuple, Dict, Any
from models.example import Example


class ExampleExtractor:
    """
    Extracts code examples from Markdown content.
    
    Identifies code blocks and extracts code, results, and metadata.
    """
    
    def __init__(self, content: str):
        """
        Initialize extractor with Markdown content.
        
        Args:
            content: Markdown content string
        """
        self.content = content
    
    def extract(self, skill_name: str) -> List[Example]:
        """
        Extract examples from Markdown content.
        
        Args:
            skill_name: Name of the associated skill
            
        Returns:
            List of Example objects
        """
        examples = []
        
        # Find all code blocks
        code_blocks = self._find_code_blocks()
        
        for i, block in enumerate(code_blocks):
            example_type = block.get('language', 'text')
            code = block['code']
            title = block.get('title')
            
            # Try to find result after this code block
            result = self._find_result_after_block(block['end_pos'])
            
            # Try to find description before this code block
            description = self._find_description_before_block(block['start_pos'])
            
            example = Example(
                skill_name=skill_name,
                code=code,
                example_type=example_type,
                title=title,
                result=result,
                description=description,
                order_index=i
            )
            examples.append(example)
        
        return examples
    
    def _find_code_blocks(self) -> List[Dict[str, Any]]:
        """
        Find all code blocks in the content.
        
        Returns:
            List of dictionaries with code block information
        """
        blocks = []
        
        # Pattern to match code blocks: ```language\ncode\n```
        pattern = r'```(\w+)?\n(.*?)```'
        
        for match in re.finditer(pattern, self.content, re.DOTALL):
            language = match.group(1) or 'text'
            code = match.group(2).strip()
            
            # Skip empty code blocks
            if not code:
                continue
            
            # Find title (text before code block on same line or previous line)
            title = self._find_title_for_block(match.start())
            
            blocks.append({
                'language': language,
                'code': code,
                'title': title,
                'start_pos': match.start(),
                'end_pos': match.end()
            })
        
        return blocks
    
    def _find_title_for_block(self, block_start: int) -> Optional[str]:
        """
        Find title for a code block.
        
        Looks for text before the code block that might be a title.
        
        Args:
            block_start: Start position of code block in content
            
        Returns:
            Title string or None
        """
        # Look backwards from code block start
        before_text = self.content[:block_start].strip()
        
        if not before_text:
            return None
        
        # Get last few lines before code block
        lines = before_text.split('\n')
        
        # Look for lines that might be titles (short, not code, not empty)
        for line in reversed(lines[-5:]):  # Check last 5 lines
            line = line.strip()
            
            # Skip empty lines, code blocks, list items
            if not line or line.startswith('```') or line.startswith('-') or line.startswith('*'):
                continue
            
            # Skip very long lines (probably not titles)
            if len(line) > 100:
                continue
            
            # Skip lines that are clearly part of code or formatting
            if line.startswith('|') or line.startswith('#') or '```' in line:
                continue
            
            # Found a potential title
            # Remove markdown formatting
            title = re.sub(r'\*\*([^*]+)\*\*', r'\1', line)
            title = re.sub(r'`([^`]+)`', r'\1', title)
            title = title.strip()
            
            if title and len(title) < 80:
                return title
        
        return None
    
    def _find_result_after_block(self, block_end: int) -> Optional[str]:
        """
        Find execution result after a code block.
        
        Looks for text or code blocks immediately after the code block.
        
        Args:
            block_end: End position of code block in content
            
        Returns:
            Result string or None
        """
        # Look forward from code block end
        after_text = self.content[block_end:].strip()
        
        if not after_text:
            return None
        
        lines = after_text.split('\n')
        
        # Look for result indicators
        result_indicators = [
            '查询结果如下：',
            'Query results:',
            '结果如下：',
            'Result:',
            'Output:',
            '错误信息如下：',
            'Error:',
        ]
        
        result_start = None
        for i, line in enumerate(lines[:10]):  # Check first 10 lines
            line_lower = line.lower().strip()
            for indicator in result_indicators:
                if indicator.lower() in line_lower:
                    result_start = i + 1
                    break
            if result_start:
                break
        
        if result_start is None:
            return None
        
        # Extract result (could be text or code block)
        result_lines = lines[result_start:result_start + 20]  # Get up to 20 lines
        
        # Check if next line starts a code block
        if result_lines and result_lines[0].strip().startswith('```'):
            # Extract code block content
            result_text = '\n'.join(result_lines)
            code_block_match = re.search(r'```\w*\n(.*?)```', result_text, re.DOTALL)
            if code_block_match:
                return code_block_match.group(1).strip()
        
        # Otherwise, return text lines (up to first empty line or next section)
        result_text = []
        for line in result_lines:
            line = line.strip()
            if not line:
                break
            if line.startswith('##'):
                break
            result_text.append(line)
        
        return '\n'.join(result_text) if result_text else None
    
    def _find_description_before_block(self, block_start: int) -> Optional[str]:
        """
        Find description before a code block.
        
        Args:
            block_start: Start position of code block in content
            
        Returns:
            Description string or None
        """
        # Look backwards from code block start
        before_text = self.content[:block_start].strip()
        
        if not before_text:
            return None
        
        lines = before_text.split('\n')
        
        # Get last few non-empty lines before code block
        description_lines = []
        for line in reversed(lines[-3:]):  # Check last 3 lines
            line = line.strip()
            
            # Skip empty lines, code blocks, list items, headers
            if not line or line.startswith('```') or line.startswith('-') or line.startswith('*') or line.startswith('#'):
                continue
            
            # Skip very long lines
            if len(line) > 200:
                continue
            
            description_lines.insert(0, line)
        
        if description_lines:
            description = ' '.join(description_lines)
            # Clean up markdown formatting
            description = re.sub(r'\*\*([^*]+)\*\*', r'\1', description)
            description = re.sub(r'`([^`]+)`', r'\1', description)
            return description.strip()
        
        return None
