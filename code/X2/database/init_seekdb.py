#!/usr/bin/env python3
"""
Initialize seekdb collections for X2 Skill storage.

Usage:
    python init_seekdb.py [--db-path <path>] [--force]
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from storage import create_storage
from database.collections import DEFAULT_SEEKDB_PATH
from database.seekdb_client import check_connection, ensure_database


def main():
    parser = argparse.ArgumentParser(description="Initialize X2 seekdb Skill storage")
    parser.add_argument(
        "--db-path",
        default=DEFAULT_SEEKDB_PATH,
        help=f"seekdb path (default: {DEFAULT_SEEKDB_PATH})",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Recreate collections if they already exist",
    )
    args = parser.parse_args()

    ok, message = check_connection(args.db_path)
    if not ok:
        print(message)
        sys.exit(1)

    ensure_database()

    storage = create_storage(args.db_path)
    storage.init(force=args.force)
    print(f"✓ seekdb ready: {args.db_path}")
    summary = storage.get_migration_summary()
    print(f"  Skills: {summary['skill_count']}, Rules: {summary['rule_count']}, "
          f"Examples: {summary['example_count']}")


if __name__ == "__main__":
    main()
