"""
Filter builder utilities for metadata and document filtering

Supports:
- Metadata filters: $eq, $lt, $gt, $lte, $gte, $ne, $in, $nin
- Logical operators: $or, $and, $not
- Document filters: $contains, $regex
"""

import json
from typing import Any, ClassVar


class FilterBuilder:
    """Build SQL WHERE clauses from filter dictionaries"""

    # Comparison operators mapping
    COMPARISON_OPS: ClassVar[dict[str, str]] = {
        "$eq": "=",
        "$lt": "<",
        "$gt": ">",
        "$lte": "<=",
        "$gte": ">=",
        "$ne": "!=",
    }

    # Logical operators
    LOGICAL_OPS: ClassVar[list[str]] = ["$and", "$or", "$not"]

    # Document operators
    DOCUMENT_OPS: ClassVar[list[str]] = ["$contains", "$regex"]

    @staticmethod
    def build_metadata_filter(where: dict[str, Any], metadata_column: str = "metadata") -> tuple[str, list[Any]]:
        """
        Build WHERE clause for metadata filtering

        Args:
            where: Filter dictionary with operators like $eq, $lt, $gt, $lte, $gte, $ne, $in, $nin, $and, $or, $not
            metadata_column: Name of metadata column (default: "metadata")

        Returns:
            Tuple of (where_clause, params) for parameterized query

        Examples:
            where = {"age": {"$gte": 18}}
            -> ("JSON_EXTRACT(metadata, '$.age') >= %s", [18])

            where = {"$and": [{"age": {"$gte": 18}}, {"city": "Beijing"}]}
            -> ("(JSON_EXTRACT(metadata, '$.age') >= %s AND JSON_EXTRACT(metadata, '$.city') = %s)", [18, "Beijing"])
        """
        if not where:
            return "", []

        return FilterBuilder._build_condition(where, metadata_column)

    @staticmethod
    def build_document_filter(
        where_document: dict[str, Any], document_column: str = "document"
    ) -> tuple[str, list[Any]]:
        """
        Build WHERE clause for document filtering

        Args:
            where_document: Filter dictionary with $contains, $regex, $and, $or operators
            document_column: Name of document column (default: "document")

        Returns:
            Tuple of (where_clause, params) for parameterized query

        Examples:
            where_document = {"$contains": "python"}
            -> ("MATCH(document) AGAINST (%s IN NATURAL LANGUAGE MODE)", ["python"])

            where_document = {"$regex": "^hello.*world$"}
            -> ("document REGEXP %s", ["^hello.*world$"])
        """
        if not where_document:
            return "", []

        return FilterBuilder._build_document_condition(where_document, document_column)

    @staticmethod
    def _build_condition(  # noqa: C901
        condition: dict[str, Any],
        metadata_column: str,
        params: list[Any] | None = None,
    ) -> tuple[str, list[Any]]:
        """Recursively build condition from nested dictionary"""
        if params is None:
            params = []

        clauses = []

        for key, value in condition.items():
            if key in FilterBuilder.LOGICAL_OPS:
                # Handle logical operators
                if key == "$and":
                    sub_clauses = []
                    for sub_condition in value:
                        sub_clause, params = FilterBuilder._build_condition(sub_condition, metadata_column, params)
                        sub_clauses.append(sub_clause)
                    clauses.append(f"({' AND '.join(sub_clauses)})")

                elif key == "$or":
                    sub_clauses = []
                    for sub_condition in value:
                        sub_clause, params = FilterBuilder._build_condition(sub_condition, metadata_column, params)
                        sub_clauses.append(sub_clause)
                    clauses.append(f"({' OR '.join(sub_clauses)})")

                elif key == "$not":
                    sub_clause, params = FilterBuilder._build_condition(value, metadata_column, params)
                    clauses.append(f"NOT ({sub_clause})")

            elif isinstance(value, dict):
                # Handle comparison operators
                for op, op_value in value.items():
                    if op == "$eq":
                        # Use JSON_OVERLAPS for $eq to support both scalar and array fields
                        json_value = json.dumps([op_value])
                        clauses.append(f"JSON_OVERLAPS(JSON_EXTRACT({metadata_column}, '$.{key}'), CAST(%s AS JSON))")
                        params.append(json_value)
                    elif op == "$ne":
                        # Use NOT JSON_OVERLAPS for $ne to support both scalar and array fields
                        json_value = json.dumps([op_value])
                        clauses.append(
                            f"NOT JSON_OVERLAPS(JSON_EXTRACT({metadata_column}, '$.{key}'), CAST(%s AS JSON))"
                        )
                        params.append(json_value)
                    elif op in FilterBuilder.COMPARISON_OPS:
                        sql_op = FilterBuilder.COMPARISON_OPS[op]
                        clauses.append(f"JSON_EXTRACT({metadata_column}, '$.{key}') {sql_op} %s")
                        params.append(op_value)

                    elif op == "$in":
                        # Parameter validation
                        if not isinstance(op_value, (list, tuple)):
                            op_value = [op_value]
                        if len(op_value) == 0:
                            clauses.append("FALSE")  # empty $in should match nothing
                            continue

                        # Use single JSON_OVERLAPS (supports both scalar and array fields)
                        json_array = json.dumps(list(op_value))
                        clauses.append(f"JSON_OVERLAPS(JSON_EXTRACT({metadata_column}, '$.{key}'), CAST(%s AS JSON))")
                        params.append(json_array)

                    elif op == "$nin":
                        # Parameter validation
                        if not isinstance(op_value, (list, tuple)):
                            op_value = [op_value]
                        if len(op_value) == 0:
                            continue  # empty $nin matches everything

                        # Use single JSON_OVERLAPS (supports both scalar and array fields)
                        json_array = json.dumps(list(op_value))
                        clauses.append(
                            f"NOT JSON_OVERLAPS(JSON_EXTRACT({metadata_column}, '$.{key}'), CAST(%s AS JSON))"
                        )
                        params.append(json_array)

            else:
                # Direct equality comparison (no operator specified)
                # Use JSON_OVERLAPS to support both scalar and array fields
                json_value = json.dumps([value])
                clauses.append(f"JSON_OVERLAPS(JSON_EXTRACT({metadata_column}, '$.{key}'), CAST(%s AS JSON))")
                params.append(json_value)

        where_clause = " AND ".join(clauses) if clauses else "1=1"
        return where_clause, params

    @staticmethod
    def _build_document_condition(
        condition: dict[str, Any],
        document_column: str,
        params: list[Any] | None = None,
    ) -> tuple[str, list[Any]]:
        """Build document filter condition"""
        if params is None:
            params = []

        clauses = []

        for key, value in condition.items():
            if key == "$contains":
                # Full-text search using MATCH AGAINST
                clauses.append(f"MATCH({document_column}) AGAINST (%s IN NATURAL LANGUAGE MODE)")
                params.append(value)

            elif key == "$regex":
                # Regular expression matching
                clauses.append(f"{document_column} REGEXP %s")
                params.append(value)

            elif key == "$and":
                sub_clauses = []
                for sub_condition in value:
                    sub_clause, params = FilterBuilder._build_document_condition(sub_condition, document_column, params)
                    sub_clauses.append(sub_clause)
                clauses.append(f"({' AND '.join(sub_clauses)})")

            elif key == "$or":
                sub_clauses = []
                for sub_condition in value:
                    sub_clause, params = FilterBuilder._build_document_condition(sub_condition, document_column, params)
                    sub_clauses.append(sub_clause)
                clauses.append(f"({' OR '.join(sub_clauses)})")

        where_clause = " AND ".join(clauses) if clauses else "1=1"
        return where_clause, params

    @staticmethod
    def combine_filters(
        metadata_filter: tuple[str, list[Any]], document_filter: tuple[str, list[Any]]
    ) -> tuple[str, list[Any]]:
        """
        Combine metadata and document filters

        Args:
            metadata_filter: Tuple of (where_clause, params) for metadata
            document_filter: Tuple of (where_clause, params) for document

        Returns:
            Combined (where_clause, params)
        """
        meta_clause, meta_params = metadata_filter
        doc_clause, doc_params = document_filter

        clauses = []
        all_params = []

        if meta_clause:
            clauses.append(meta_clause)
            all_params.extend(meta_params)

        if doc_clause:
            clauses.append(doc_clause)
            all_params.extend(doc_params)

        if clauses:
            combined_clause = " AND ".join(clauses)
            return combined_clause, all_params
        else:
            return "", []

    @staticmethod
    def build_search_filter(
        where: dict[str, Any] | None,
    ) -> list[dict[str, Any]] | None:
        """
        Build search_params filter format from where condition for hybrid search

        Args:
            where: Filter dictionary with operators like $eq, $lt, $gt, $lte, $gte, $ne, $in, $nin, $and, $or, $not

        Returns:
            List of filter conditions in search_params format, or None if where is empty

        Examples:
            where = {"category": {"$eq": "science"}}
            -> [{"term": {"metadata.category": {"value": "science"}}}]

            where = {"$and": [{"page": {"$gte": 5}}, {"page": {"$lte": 10}}]}
            -> [{"bool": {"must": [{"range": {"metadata.page": {"gte": 5}}}, {"range": {"metadata.page": {"lte": 10}}}]}}]
        """
        if not where:
            return None

        filter_condition = FilterBuilder._build_search_filter_condition(where)
        if filter_condition:
            return [filter_condition]
        return None

    @staticmethod
    def _build_search_filter_condition(  # noqa: C901
        condition: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Recursively build search_params filter condition from nested dictionary"""
        if not condition:
            return None

        # Handle logical operators
        if "$and" in condition:
            must_conditions = []
            for sub_condition in condition["$and"]:
                sub_filter = FilterBuilder._build_search_filter_condition(sub_condition)
                if sub_filter:
                    must_conditions.append(sub_filter)
            if must_conditions:
                return {"bool": {"must": must_conditions}}
            return None

        if "$or" in condition:
            should_conditions = []
            for sub_condition in condition["$or"]:
                sub_filter = FilterBuilder._build_search_filter_condition(sub_condition)
                if sub_filter:
                    should_conditions.append(sub_filter)
            if should_conditions:
                return {"bool": {"should": should_conditions}}
            return None

        if "$not" in condition:
            not_filter = FilterBuilder._build_search_filter_condition(condition["$not"])
            if not_filter:
                return {"bool": {"must_not": [not_filter]}}
            return None

        # Handle field conditions
        result = {"bool": {"must": [], "should": [], "must_not": []}}
        has_conditions = False

        for key, value in condition.items():
            if key in FilterBuilder.LOGICAL_OPS:
                continue

            field_name = f"metadata.{key}"

            if isinstance(value, dict):
                # Handle comparison operators
                range_conditions = {}
                term_conditions = []
                in_conditions = []
                nin_conditions = []

                for op, op_value in value.items():
                    if op == "$eq":
                        term_conditions.append({"term": {field_name: {"value": op_value}}})
                        has_conditions = True
                    elif op == "$ne":
                        result["bool"]["must_not"].append({"term": {field_name: {"value": op_value}}})
                        has_conditions = True
                    elif op == "$lt":
                        range_conditions["lt"] = op_value
                        has_conditions = True
                    elif op == "$lte":
                        range_conditions["lte"] = op_value
                        has_conditions = True
                    elif op == "$gt":
                        range_conditions["gt"] = op_value
                        has_conditions = True
                    elif op == "$gte":
                        range_conditions["gte"] = op_value
                        has_conditions = True
                    elif op == "$in":
                        for val in op_value:
                            in_conditions.append({"term": {field_name: {"value": val}}})
                        has_conditions = True
                    elif op == "$nin":
                        for val in op_value:
                            nin_conditions.append({"term": {field_name: {"value": val}}})
                        has_conditions = True

                if range_conditions:
                    result["bool"]["must"].append({"range": {field_name: range_conditions}})
                if term_conditions:
                    result["bool"]["must"].extend(term_conditions)
                if in_conditions:
                    result["bool"]["should"].extend(in_conditions)
                if nin_conditions:
                    result["bool"]["must_not"].extend(nin_conditions)
            else:
                # Direct equality
                result["bool"]["must"].append({"term": {field_name: {"value": value}}})
                has_conditions = True

        if not has_conditions:
            return None

        # Clean up empty arrays
        if not result["bool"]["must"]:
            del result["bool"]["must"]
        if not result["bool"]["should"]:
            del result["bool"]["should"]
        if not result["bool"]["must_not"]:
            del result["bool"]["must_not"]

        # If only one type of condition, simplify
        if len(result["bool"]) == 1:
            key = next(iter(result["bool"]))
            conditions = result["bool"][key]
            if len(conditions) == 1:
                return conditions[0]
            return {"bool": {key: conditions}}

        return result
