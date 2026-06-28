#!/usr/bin/env python3
"""
Check seekdb connectivity before running X2 demos.

Usage:
    python database/check_seekdb.py
    python database/check_seekdb.py --verbose
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from database.collections import DEFAULT_SEEKDB_PATH
from database.seekdb_client import (
    check_connection,
    resolve_mode,
    server_endpoint,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Check seekdb connectivity for X2")
    parser.add_argument(
        "--db-path",
        default=DEFAULT_SEEKDB_PATH,
        help=f"Embedded data path (default: {DEFAULT_SEEKDB_PATH})",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print resolved connection settings",
    )
    args = parser.parse_args()

    mode = resolve_mode()
    print(f"模式: {mode}")
    if args.verbose and mode == "server":
        host, port = server_endpoint()
        print(f"  host: {host}")
        print(f"  port: {port}")

    ok, message = check_connection(args.db_path)
    print(message)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
