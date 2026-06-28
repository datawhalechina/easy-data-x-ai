"""
CLI main: argument parsing, connection factory, and subcommand dispatch.
"""

import argparse
import json
import os
import sys
from typing import Any

from .. import AdminClient, Client
from ..client.admin_client import _AdminClientProxy, _ClientProxy
from ..client.configuration import HNSWConfiguration


def _add_connection_args(parser: argparse.ArgumentParser) -> None:
    """Add global connection options (embedded vs server)."""
    g = parser.add_argument_group("connection (choose one)")
    g.add_argument(
        "--path",
        metavar="DIR",
        default=None,
        help="Embedded mode: path to seekdb data directory (default: seekdb.db in cwd)",
    )
    g.add_argument("--host", default=None, help="Server mode: host (e.g. localhost)")
    g.add_argument("--port", type=int, default=2881, help="Server mode: port (default: 2881)")
    g.add_argument("--tenant", default="sys", help="Server mode: tenant (default: sys)")
    g.add_argument("--database", "-d", default="test", help="Database name (default: test)")
    g.add_argument("--user", default="root", help="Server mode: user (default: root)")
    g.add_argument(
        "--password",
        "-p",
        default=None,
        help="Server mode: password (or set SEEKDB_PASSWORD)",
    )
    parser.add_argument(
        "-o",
        "--output",
        choices=["table", "json"],
        default="table",
        help="Output format (default: table)",
    )


def _make_client(args: argparse.Namespace) -> _ClientProxy:
    """Build Client from parsed args (for collection operations)."""
    password = args.password or os.environ.get("SEEKDB_PASSWORD", "")
    return Client(
        path=args.path,
        host=args.host,
        port=args.port,
        tenant=args.tenant,
        database=args.database,
        user=args.user,
        password=password,
    )


def _make_admin(args: argparse.Namespace) -> _AdminClientProxy:
    """Build AdminClient from parsed args (for db operations)."""
    password = args.password or os.environ.get("SEEKDB_PASSWORD", "")
    return AdminClient(
        path=args.path,
        host=args.host,
        port=args.port,
        tenant=args.tenant,
        user=args.user,
        password=password,
    )


def _execute_sql(client: _ClientProxy, sql: str) -> Any:
    """Run raw SQL using the underlying server (for debug)."""
    server = client._server
    return server._execute(sql)


def _print_table(rows: list[dict[str, Any]] | None, columns: list[str] | None = None) -> None:
    """Print rows as a simple text table."""
    if not rows:
        print("(0 rows)")
        return
    if columns is None:
        columns = list(rows[0].keys()) if rows else []
    col_widths = [max(len(str(c)), 3) for c in columns]
    for r in rows:
        for i, c in enumerate(columns):
            val = r.get(c, "")
            if isinstance(val, (dict, list)):
                val = json.dumps(val, ensure_ascii=False)[:40]
            col_widths[i] = max(col_widths[i], min(len(str(val)), 50))
    fmt = "  ".join(f"%-{w}s" for w in col_widths)
    print(fmt % tuple(columns))
    print("-" * (sum(col_widths) + 2 * (len(columns) - 1)))
    for r in rows:
        cells = []
        for c in columns:
            v = r.get(c, "")
            if isinstance(v, (dict, list)):
                v = json.dumps(v, ensure_ascii=False)[:40]
            s = str(v)
            if len(s) > 50:
                s = s[:47] + "..."
            cells.append(s)
        print(fmt % tuple(cells))


def _print_json(obj: Any) -> None:
    """Print object as JSON."""
    if hasattr(obj, "__iter__") and not isinstance(obj, (str, dict)):
        obj = list(obj)
    print(json.dumps(obj, indent=2, ensure_ascii=False, default=str))


# ---------- Commands ----------


def cmd_db_list(args: argparse.Namespace) -> int:
    """List databases."""
    admin = _make_admin(args)
    try:
        dbs = admin.list_databases()
        rows = [{"name": d.name, "tenant": d.tenant or ""} for d in dbs]
        if args.output == "json":
            _print_json(rows)
        else:
            _print_table(rows, ["name", "tenant"])
        return 0
    finally:
        admin._server._cleanup()


def cmd_db_create(args: argparse.Namespace) -> int:
    """Create database."""
    admin = _make_admin(args)
    try:
        admin.create_database(args.name, tenant=args.tenant)
        print(f"Created database: {args.name}")
        return 0
    finally:
        admin._server._cleanup()


def cmd_db_delete(args: argparse.Namespace) -> int:
    """Delete database."""
    admin = _make_admin(args)
    try:
        admin.delete_database(args.name, tenant=args.tenant)
        print(f"Deleted database: {args.name}")
        return 0
    finally:
        admin._server._cleanup()


def cmd_collections_list(args: argparse.Namespace) -> int:
    """List collections."""
    client = _make_client(args)
    try:
        colls = client.list_collections()
        rows = [
            {
                "name": c.name,
                "dimension": c.dimension or "",
                "distance": c.distance or "",
            }
            for c in colls
        ]
        if args.output == "json":
            _print_json(rows)
        else:
            _print_table(rows, ["name", "dimension", "distance"])
        return 0
    finally:
        client._server._cleanup()


def cmd_collections_create(args: argparse.Namespace) -> int:
    """Create collection."""
    client = _make_client(args)
    try:
        config = HNSWConfiguration(dimension=args.dimension) if args.dimension else None
        client.create_collection(args.name, configuration=config)
        print(f"Created collection: {args.name}")
        return 0
    finally:
        client._server._cleanup()


def cmd_collections_delete(args: argparse.Namespace) -> int:
    """Delete collection."""
    client = _make_client(args)
    try:
        client.delete_collection(args.name)
        print(f"Deleted collection: {args.name}")
        return 0
    finally:
        client._server._cleanup()


def cmd_collections_info(args: argparse.Namespace) -> int:
    """Show collection info (schema, count, sample)."""
    client = _make_client(args)
    try:
        if not client.has_collection(args.name):
            print(f"Collection not found: {args.name}", file=sys.stderr)
            return 1
        coll = client.get_collection(args.name)
        info = {
            "name": coll.name,
            "dimension": coll.dimension,
            "distance": coll.distance,
            "metadata": coll.metadata,
            "count": coll.count(),
        }
        if args.output == "json":
            sample = coll.peek(limit=args.sample) if args.sample and info["count"] > 0 else {}
            payload = {"info": info, "sample": sample}
            _print_json(payload)
        else:
            print(f"Name:     {info['name']}")
            print(f"Dimension: {info['dimension']}")
            print(f"Distance: {info['distance']}")
            print(f"Count:    {info['count']}")
            if info.get("metadata"):
                print(f"Metadata: {info['metadata']}")
            if args.sample and info["count"] > 0:
                sample = coll.peek(limit=args.sample)
                print("\nSample (peek):")
                for i in range(len(sample["ids"])):
                    print(f"  id={sample['ids'][i]}")
                    if sample.get("documents"):
                        doc = sample["documents"][i]
                        print(f"    document: {str(doc)[:80]}...")
                    if sample.get("metadatas"):
                        print(f"    metadata: {sample['metadatas'][i]}")
        return 0
    finally:
        client._server._cleanup()


def cmd_sql(args: argparse.Namespace) -> int:
    """Execute raw SQL (debug)."""
    client = _make_client(args)
    try:
        result = _execute_sql(client, args.sql)
        if result is None:
            print("OK")
            return 0
        if args.output == "json":
            # result may be list of tuples or list of dicts
            if not result:
                _print_json([])
            elif hasattr(result[0], "keys"):
                _print_json(result)
            else:
                _print_json([list(r) for r in result])
        else:
            if not result:
                print("(0 rows)")
            elif hasattr(result[0], "keys"):
                _print_table(result)
            else:
                cols = [f"col_{i}" for i in range(len(result[0]))]
                _print_table([dict(zip(cols, r, strict=True)) for r in result], cols)
        return 0
    finally:
        client._server._cleanup()


def cmd_query(args: argparse.Namespace) -> int:
    """Query collection by text or embedding."""
    client = _make_client(args)
    try:
        if not client.has_collection(args.collection):
            print(f"Collection not found: {args.collection}", file=sys.stderr)
            return 1
        coll = client.get_collection(args.collection)
        if args.text:
            res = coll.query(
                query_texts=[args.text], n_results=args.n, include=args.include or ["documents", "metadatas"]
            )
        else:
            print("Specify --text for query by text (embedding not supported in CLI)", file=sys.stderr)
            return 1
        if args.output == "json":
            _print_json(res)
        else:
            ids = res.get("ids", [[]])[0]
            docs = res.get("documents", [[]])[0] if res.get("documents") else []
            metas = res.get("metadatas", [[]])[0] if res.get("metadatas") else []
            dists = res.get("distances", [[]])[0] if res.get("distances") else []
            for i in range(len(ids)):
                print(f"id={ids[i]} distance={dists[i] if i < len(dists) else ''}")
                if i < len(docs):
                    print(f"  document: {str(docs[i])[:80]}...")
                if i < len(metas):
                    print(f"  metadata: {metas[i]}")
        return 0
    finally:
        client._server._cleanup()


def cmd_get(args: argparse.Namespace) -> int:
    """Get documents from collection by ids or limit."""
    client = _make_client(args)
    try:
        if not client.has_collection(args.collection):
            print(f"Collection not found: {args.collection}", file=sys.stderr)
            return 1
        coll = client.get_collection(args.collection)
        ids = None
        if args.ids:
            ids = [x.strip() for x in args.ids.split(",") if x.strip()]
        res = coll.get(
            ids=ids,
            limit=args.limit,
            include=args.include or ["documents", "metadatas"],
        )
        if args.output == "json":
            _print_json(res)
        else:
            for i in range(len(res.get("ids", []))):
                print(f"id={res['ids'][i]}")
                if res.get("documents") and i < len(res["documents"]):
                    print(f"  document: {str(res['documents'][i])[:80]}...")
                if res.get("metadatas") and i < len(res["metadatas"]):
                    print(f"  metadata: {res['metadatas'][i]}")
        return 0
    finally:
        client._server._cleanup()


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="pyseekdb",
        description="seekdb CLI: debug and manage collections/databases (see spec.md).",
    )
    _add_connection_args(parser)
    sub = parser.add_subparsers(dest="command", required=True, help="command")

    # db
    db = sub.add_parser("db", help="Database (admin) operations")
    db_sub = db.add_subparsers(dest="db_command", required=True)
    db_list = db_sub.add_parser("list", help="List databases")
    db_list.set_defaults(func=cmd_db_list)
    db_create = db_sub.add_parser("create", help="Create database")
    db_create.add_argument("name", help="Database name")
    db_create.set_defaults(func=cmd_db_create)
    db_delete = db_sub.add_parser("delete", help="Delete database")
    db_delete.add_argument("name", help="Database name")
    db_delete.set_defaults(func=cmd_db_delete)

    # collections (and alias coll)
    def _add_collection_subparsers(parent: argparse.ArgumentParser) -> None:
        csub = parent.add_subparsers(dest="coll_command", required=True)
        csub.add_parser("list", help="List collections").set_defaults(func=cmd_collections_list)
        create = csub.add_parser("create", help="Create collection")
        create.add_argument("name", help="Collection name")
        create.add_argument("--dimension", type=int, default=None, help="Vector dimension")
        create.set_defaults(func=cmd_collections_create)
        delete = csub.add_parser("delete", help="Delete collection")
        delete.add_argument("name", help="Collection name")
        delete.set_defaults(func=cmd_collections_delete)
        info = csub.add_parser("info", help="Show collection info and optional sample")
        info.add_argument("name", help="Collection name")
        info.add_argument("--sample", type=int, default=0, metavar="N", help="Peek first N rows")
        info.set_defaults(func=cmd_collections_info)

    _add_collection_subparsers(sub.add_parser("collections", help="Collection operations"))
    _add_collection_subparsers(sub.add_parser("coll", help="Alias for collections"))

    # sql
    sql_p = sub.add_parser("sql", help="Execute raw SQL (debug)")
    _add_connection_args(sql_p)
    sql_p.add_argument("sql", help="SQL statement")
    sql_p.set_defaults(func=cmd_sql)

    # query
    query_p = sub.add_parser("query", help="Query collection by text")
    _add_connection_args(query_p)
    query_p.add_argument("collection", help="Collection name")
    query_p.add_argument(
        "--text", "-t", required=True, help="Query text (will be embedded if collection has embedding)"
    )
    query_p.add_argument("--n", type=int, default=10, help="Number of results (default: 10)")
    query_p.add_argument("--include", nargs="+", default=None, help="Include fields: documents, metadatas, embeddings")
    query_p.set_defaults(func=cmd_query)

    # get
    get_p = sub.add_parser("get", help="Get documents from collection")
    _add_connection_args(get_p)
    get_p.add_argument("collection", help="Collection name")
    get_p.add_argument("--ids", default=None, help="Comma-separated IDs")
    get_p.add_argument("--limit", type=int, default=10, help="Max rows (default: 10)")
    get_p.add_argument("--include", nargs="+", default=None, help="Include fields")
    get_p.set_defaults(func=cmd_get)

    args = parser.parse_args(argv)
    return args.func(args)
