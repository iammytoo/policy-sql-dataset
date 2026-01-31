"""Negative example generation for policy violation testing."""

import re
from typing import Any

from .types import NegativeExample, PolicyType, TableSchema, Violation


def generate_negative(
    query: str,
    sql: dict[str, Any],
    policies: dict[str, PolicyType],
    schema: TableSchema,
) -> list[NegativeExample]:
    """Generate negative example (max 1) with policy violations."""
    # N1: Add Hidden column to SELECT (highest priority)
    negative = _try_add_hidden(query, sql, policies, schema)
    if negative:
        return [negative]

    # N2: Unwrap aggregation from AggOnly column
    negative = _try_unwrap_agg(query, policies)
    if negative:
        return [negative]

    # N3: Add JoinOnly column to SELECT
    negative = _try_add_joinonly(query, sql, policies, schema)
    if negative:
        return [negative]

    return []


def _try_add_hidden(
    query: str,
    sql: dict[str, Any],
    policies: dict[str, PolicyType],
    schema: TableSchema,
) -> NegativeExample | None:
    """Add a Hidden column to SELECT clause."""
    tables = _extract_tables(sql, schema)

    for table in tables:
        table_lower = table.lower()
        for col_key, policy in policies.items():
            col_table = col_key.split(".")[0].lower()
            if policy == "Hidden" and col_table == table_lower:
                col_name = col_key.split(".")[-1]
                # Check if column is already in query
                if col_name.lower() in query.lower():
                    continue
                new_sql = _add_to_select(query, col_name)
                violations = [
                    Violation(
                        column=col_key, role="SelectExpr", policy="Hidden", agg_id=0
                    )
                ]
                return NegativeExample(sql=new_sql, violations=violations)

    return None


def _try_unwrap_agg(
    query: str, policies: dict[str, PolicyType]
) -> NegativeExample | None:
    """Remove aggregation function from AggOnly column."""
    for col_key, policy in policies.items():
        if policy != "AggOnly":
            continue
        col_name = col_key.split(".")[-1]

        # Find AVG(col) or COUNT(col) pattern
        pattern = rf"\b(AVG|COUNT)\s*\(\s*{re.escape(col_name)}\s*\)"
        if re.search(pattern, query, re.IGNORECASE):
            new_sql = re.sub(pattern, col_name, query, count=1, flags=re.IGNORECASE)
            violations = [
                Violation(
                    column=col_key, role="SelectExpr", policy="AggOnly", agg_id=0
                )
            ]
            return NegativeExample(sql=new_sql, violations=violations)

    return None


def _try_add_joinonly(
    query: str,
    sql: dict[str, Any],
    policies: dict[str, PolicyType],
    schema: TableSchema,
) -> NegativeExample | None:
    """Add a JoinOnly column to SELECT clause."""
    tables = _extract_tables(sql, schema)

    for table in tables:
        table_lower = table.lower()
        for col_key, policy in policies.items():
            col_table = col_key.split(".")[0].lower()
            if policy == "JoinOnly" and col_table == table_lower:
                col_name = col_key.split(".")[-1]
                # Skip if already in query
                if col_name.lower() in query.lower():
                    continue
                new_sql = _add_to_select(query, col_name)
                violations = [
                    Violation(
                        column=col_key, role="SelectExpr", policy="JoinOnly", agg_id=0
                    )
                ]
                return NegativeExample(sql=new_sql, violations=violations)

    return None


def _add_to_select(query: str, col_name: str) -> str:
    """Add a column to the beginning of SELECT clause."""
    return re.sub(
        r"\bSELECT\s+", f"SELECT {col_name}, ", query, count=1, flags=re.IGNORECASE
    )


def _extract_tables(sql: dict[str, Any], schema: TableSchema) -> list[str]:
    """Extract table names from FROM clause."""
    tables: list[str] = []

    for table_unit in sql["from"]["table_units"]:
        if table_unit[0] == "table_unit":
            table_idx = table_unit[1]
            if 0 <= table_idx < len(schema.table_names):
                tables.append(schema.table_names[table_idx])
        elif table_unit[0] == "sql":
            # Subquery - recursively extract tables
            tables.extend(_extract_tables(table_unit[1], schema))

    return tables
