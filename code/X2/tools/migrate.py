#!/usr/bin/env python3
"""
Migration tool for migrating SKILL.md files to seekdb.

Usage:
    python migrate.py <skill_file> [--db-path <path>] [--force]
    python migrate.py <skills_dir> --all [--db-path <path>] [--force]
"""

import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from services import MigrationService
from storage import create_storage
from database.collections import DEFAULT_SEEKDB_PATH
from database.seekdb_client import check_connection, ensure_database


def ensure_storage(db_path: str) -> None:
    ok, message = check_connection(db_path)
    if not ok:
        print(message)
        sys.exit(1)
    ensure_database()
    storage = create_storage(db_path)
    if not storage.is_initialized():
        print(f"seekdb not initialized: {db_path}")
        print("Initializing collections...")
        storage.init(force=False)


def migrate_file(skill_file: str, db_path: str, force: bool = False):
    skill_path = Path(skill_file)
    if not skill_path.exists():
        print(f"✗ Error: File not found: {skill_file}")
        sys.exit(1)

    if skill_path.name != "SKILL.md":
        print(f"✗ Error: File must be named SKILL.md: {skill_file}")
        sys.exit(1)

    ensure_storage(db_path)
    migration_service = MigrationService(db_path)

    print(f"Migrating: {skill_file}")
    result = migration_service.migrate_skill_file(skill_file, force=force)

    if result["status"] == "success":
        print(f"✓ Success: {result['skill_name']}")
        print(f"  Rules: {result['rule_count']}")
        print(f"  Examples: {result['example_count']}")
        print(f"  Action: {result['action']}")
    elif result["status"] == "skipped":
        print(f"⚠ Skipped: {result['message']}")
    else:
        print(f"✗ Error: {result.get('error', 'Unknown error')}")
        sys.exit(1)


def migrate_directory(skills_dir: str, db_path: str, force: bool = False):
    skills_path = Path(skills_dir)
    if not skills_path.exists():
        print(f"✗ Error: Directory not found: {skills_dir}")
        sys.exit(1)

    ensure_storage(db_path)
    migration_service = MigrationService(db_path)

    print(f"Migrating all skills from: {skills_dir}")
    print("-" * 60)

    results = migration_service.migrate_directory(skills_dir, force=force)

    success_count = sum(1 for r in results if r["status"] == "success")
    skipped_count = sum(1 for r in results if r["status"] == "skipped")
    error_count = sum(1 for r in results if r["status"] == "error")

    print("-" * 60)
    print("Migration Summary:")
    print(f"  Success: {success_count}")
    print(f"  Skipped: {skipped_count}")
    print(f"  Errors: {error_count}")

    if success_count > 0:
        print("\nSuccessfully migrated:")
        for result in results:
            if result["status"] == "success":
                print(f"  ✓ {result['skill_name']}: {result['rule_count']} rules, "
                      f"{result['example_count']} examples")

    if error_count > 0:
        print("\nErrors:")
        for result in results:
            if result["status"] == "error":
                print(f"  ✗ {result.get('skill_file', 'unknown')}: {result.get('error', 'Unknown error')}")
        sys.exit(1)

    summary = migration_service.get_migration_summary()
    print("\nDatabase Summary:")
    print(f"  Total skills: {summary['skill_count']}")
    print(f"  Total rules: {summary['rule_count']}")
    print(f"  Total examples: {summary['example_count']}")
    if summary["category_counts"]:
        print(f"  By category: {summary['category_counts']}")


def main():
    parser = argparse.ArgumentParser(
        description="Migrate SKILL.md files to seekdb",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python migrate.py skills/api-doc-writing/SKILL.md
  python migrate.py skills/ --all
  python migrate.py skills/ --all --force
        """,
    )
    parser.add_argument("path", help="Path to SKILL.md file or skills directory")
    parser.add_argument("--all", action="store_true", help="Migrate all SKILL.md files in directory")
    parser.add_argument(
        "--db-path",
        default=DEFAULT_SEEKDB_PATH,
        help=f"seekdb path (default: {DEFAULT_SEEKDB_PATH})",
    )
    parser.add_argument("--force", action="store_true", help="Force update existing skills")
    args = parser.parse_args()

    path = Path(args.path)
    if args.all:
        if not path.is_dir():
            print(f"✗ Error: Path must be a directory when using --all: {args.path}")
            sys.exit(1)
        migrate_directory(str(path), args.db_path, force=args.force)
    else:
        if path.is_dir():
            print(f"✗ Error: Path is a directory. Use --all to migrate directory: {args.path}")
            sys.exit(1)
        migrate_file(str(path), args.db_path, force=args.force)


if __name__ == "__main__":
    main()
