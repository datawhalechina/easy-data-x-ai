#!/usr/bin/env python3
"""
Query tool for querying skills from seekdb.

Usage:
    python query_tool.py get <skill_name> [--db-path <path>] [--format <format>]
    python query_tool.py list [--category <cat>] [--db-path <path>]
    python query_tool.py search <keyword> [--db-path <path>]
    python query_tool.py rules <skill_name> [--db-path <path>]
    python query_tool.py examples <skill_name> [--db-path <path>]
"""

import sys
import json
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from services import QueryService, SkillService
from storage import create_storage
from database.collections import DEFAULT_SEEKDB_PATH


def ensure_storage(db_path: str) -> None:
    storage = create_storage(db_path)
    if not storage.is_initialized():
        print(f"✗ Error: seekdb not initialized: {db_path}")
        print("  Run 'python database/init_seekdb.py' first")
        print("  Or run 'python tools/migrate.py skills/ --all' to migrate skills")
        sys.exit(1)


def get_skill(skill_name: str, db_path: str, output_format: str = "text"):
    query_service = QueryService(db_path)
    skill_complete = query_service.get_skill_complete(skill_name)

    if not skill_complete:
        print(f"✗ Skill not found: {skill_name}")
        sys.exit(1)

    if output_format == "json":
        print(json.dumps(skill_complete, indent=2, default=str))
    else:
        skill = skill_complete["skill"]
        print(f"Skill: {skill['name']}")
        print(f"Description: {skill['description']}")
        print(f"Category: {skill.get('category', 'N/A')}")
        print(f"Version: {skill.get('version', 'N/A')}")
        print(f"Status: {skill.get('status', 'N/A')}")
        print(f"Rules: {skill_complete['rule_count']}")
        print(f"Examples: {skill_complete['example_count']}")
        print(f"\nContent length: {len(skill['content'])} characters")


def list_skills(category: str = None, db_path: str = None):
    skill_service = SkillService(db_path)
    skills = skill_service.list_skills(category=category)

    if not skills:
        print("No skills found.")
        if category:
            print(f"Category filter: {category}")
        sys.exit(0)

    print(f"Found {len(skills)} skill(s):")
    print("-" * 60)
    for skill in skills:
        print(f"  {skill.name}")
        print(f"    Category: {skill.category or 'N/A'}")
        desc = skill.description[:60] + ("..." if len(skill.description) > 60 else "")
        print(f"    Description: {desc}")
        print()


def search_skills(keyword: str, db_path: str):
    query_service = QueryService(db_path)
    skills = query_service.search_skills(keyword)

    if not skills:
        print(f"No skills found matching: {keyword}")
        sys.exit(0)

    print(f"Found {len(skills)} skill(s) matching '{keyword}':")
    print("-" * 60)
    for skill in skills:
        print(f"  {skill.name}")
        print(f"    Category: {skill.category or 'N/A'}")
        desc = skill.description[:60] + ("..." if len(skill.description) > 60 else "")
        print(f"    Description: {desc}")
        print()


def get_rules(skill_name: str, db_path: str):
    query_service = QueryService(db_path)
    rules = query_service.get_rules_by_skill(skill_name)

    if not rules:
        print(f"No rules found for skill: {skill_name}")
        sys.exit(0)

    print(f"Rules for '{skill_name}': {len(rules)} rule(s)")
    print("-" * 60)
    for i, rule in enumerate(rules, 1):
        print(f"{i}. [{rule.rule_type}] {rule.rule_key}")
        print(f"   Value: {rule.rule_value[:80]}...")
        if rule.rule_description:
            print(f"   Description: {rule.rule_description[:60]}...")
        print(f"   Priority: {rule.priority}")
        print()


def get_examples(skill_name: str, db_path: str):
    query_service = QueryService(db_path)
    examples = query_service.get_examples_by_skill(skill_name)

    if not examples:
        print(f"No examples found for skill: {skill_name}")
        sys.exit(0)

    print(f"Examples for '{skill_name}': {len(examples)} example(s)")
    print("-" * 60)
    for i, example in enumerate(examples, 1):
        print(f"{i}. Type: {example.example_type or 'text'}")
        if example.title:
            print(f"   Title: {example.title}")
        print(f"   Code: {example.code[:80]}...")
        if example.result:
            print(f"   Result: {example.result[:80]}...")
        print()


def main():
    parser = argparse.ArgumentParser(description="Query skills from seekdb")
    parser.add_argument(
        "--db-path",
        default=DEFAULT_SEEKDB_PATH,
        help=f"seekdb path (default: {DEFAULT_SEEKDB_PATH})",
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    get_parser = subparsers.add_parser("get", help="Get skill information")
    get_parser.add_argument("skill_name", help="Skill name")
    get_parser.add_argument("--format", choices=["text", "json"], default="text")

    list_parser = subparsers.add_parser("list", help="List all skills")
    list_parser.add_argument("--category", help="Filter by category")

    search_parser = subparsers.add_parser("search", help="Search skills (hybrid)")
    search_parser.add_argument("keyword", help="Search query")

    rules_parser = subparsers.add_parser("rules", help="Get rules for a skill")
    rules_parser.add_argument("skill_name", help="Skill name")

    examples_parser = subparsers.add_parser("examples", help="Get examples for a skill")
    examples_parser.add_argument("skill_name", help="Skill name")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    ensure_storage(args.db_path)

    if args.command == "get":
        get_skill(args.skill_name, args.db_path, args.format)
    elif args.command == "list":
        list_skills(category=args.category, db_path=args.db_path)
    elif args.command == "search":
        search_skills(args.keyword, args.db_path)
    elif args.command == "rules":
        get_rules(args.skill_name, args.db_path)
    elif args.command == "examples":
        get_examples(args.skill_name, args.db_path)


if __name__ == "__main__":
    main()
