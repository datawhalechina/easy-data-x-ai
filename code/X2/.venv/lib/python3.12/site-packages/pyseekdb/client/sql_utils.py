"""
Utility functions and classes for SQL string generation and escaping in seekdb client.

Provides helpers to safely stringify values and SQL identifiers for insertion into SQL expressions.
"""

from collections.abc import Sequence
from typing import Any

from pymysql.converters import escape_string

from .query_types import QueryHint


def escape_percent_for_sql(value: str) -> str:
    """
    Escape percent signs in SQL string values to prevent format string interpretation.

    When pymysql's cursor.execute() processes SQL strings, it may interpret % as format
    specifiers. This function escapes % to %% to prevent that.

    Args:
        value: String value that may contain % characters

    Returns:
        String with % escaped as %%
    """
    return value.replace("%", "%%")


def is_query_sql(sql: str) -> bool:
    if not sql:
        return False
    sql_upper = sql.strip().upper()
    return (
        sql_upper.startswith("SELECT")
        or sql_upper.startswith("SHOW")
        or sql_upper.startswith("DESCRIBE")
        or sql_upper.startswith("DESC")
    )


def render_sql_with_params(sql: str, params: Sequence[Any]) -> str:
    if not params:
        return sql
    parts = sql.split("%s")
    placeholder_count = len(parts) - 1
    if placeholder_count != len(params):
        raise ValueError(f"Expected {placeholder_count} parameters, got {len(params)}")
    rendered_parts = [parts[0]]
    for param, part in zip(params, parts[1:], strict=True):
        if param is None:
            replacement = "NULL"
        elif isinstance(param, (bytes, bytearray, memoryview)):
            text = bytes(param).decode("utf-8", errors="replace")
            replacement = f"'{escape_string(text)}'"
        elif isinstance(param, (int, float)):
            replacement = str(param)
        elif isinstance(param, str):
            replacement = f"'{escape_string(param)}'"
        else:
            replacement = f"'{escape_string(str(param))}'"
        rendered_parts.append(replacement)
        rendered_parts.append(part)
    return "".join(rendered_parts)


def _query_hint_to_sql(query_hint: QueryHint | None, table_name: str | None = None) -> str:
    """
    Convert QueryHint to SQL HINT string for OceanBase/seekdb.

    Args:
        query_hint: QueryHint object containing hint parameters

    Returns:
        SQL HINT string in format "/*+ hint1(value1) hint2(value2) */" or empty string if no hints
    """
    if query_hint is None:
        return ""

    hints = []

    if query_hint.parallel is not None:
        hints.append(f"parallel({query_hint.parallel})")

    if query_hint.query_timeout is not None:
        # Convert seconds to microseconds for OceanBase
        timeout_microseconds = int(query_hint.query_timeout * 1_000_000)
        hints.append(f"query_timeout({timeout_microseconds})")

    if query_hint.vector_index is True and table_name:
        hints.append(f"INDEX({table_name}, idx_vec)")

    if not hints:
        return ""

    hint_str = " ".join(hints)
    return f"/*+ {hint_str} */"
