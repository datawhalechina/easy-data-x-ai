"""
pyseekdb CLI - Debug and manage seekdb collections/databases.

Usage:
  pyseekdb [OPTIONS] db list|create|delete ...
  pyseekdb [OPTIONS] collections list|create|delete|info ...
  pyseekdb [OPTIONS] sql "SELECT ..."
  pyseekdb [OPTIONS] query <collection> --text "..." [--n 5]
  pyseekdb [OPTIONS] get <collection> [--limit 10] [--ids id1,id2]
"""

from .main import main

__all__ = ["main"]
