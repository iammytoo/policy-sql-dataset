"""SQL rewriter for policy compliance."""

import re
from dataclasses import dataclass

from .types import PolicyType, TableSchema, Violation


@dataclass
class RewriteResult:
    """Result of a rewrite attempt."""

    success: bool
    sql: str | None = None
    reason: str | None = None


def rewrite(
    query: str,
    violations: list[Violation],
    schema: TableSchema,
    policies: dict[str, PolicyType],
) -> RewriteResult:
    """Attempt to rewrite SQL to resolve violations."""
    if not violations:
        return RewriteResult(True, sql=query)

    # R3: WHERE/JOIN with Hidden or AggOnly -> immediate REFUSE
    for v in violations:
        if v.role in ("WherePred", "JoinCond") and v.policy in ("Hidden", "AggOnly"):
            return RewriteResult(False, reason=f"{v.policy} column in {v.role}: {v.column}")

    # R4: AggArg with AggOnly column using non-AVG/COUNT -> REFUSE
    for v in violations:
        if v.role == "AggArg" and v.policy == "AggOnly" and v.agg_id not in (3, 5):
            return RewriteResult(
                False, reason=f"AggOnly column with non-AVG/COUNT agg: {v.column}"
            )

    # R4 also: AggArg with Hidden or JoinOnly -> REFUSE (these policies don't allow AggArg at all)
    for v in violations:
        if v.role == "AggArg" and v.policy in ("Hidden", "JoinOnly"):
            return RewriteResult(False, reason=f"{v.policy} column in AggArg: {v.column}")

    # JoinOnly in SelectExpr -> REFUSE (no useful rewrite possible)
    for v in violations:
        if v.role == "SelectExpr" and v.policy == "JoinOnly":
            return RewriteResult(False, reason=f"JoinOnly column in SelectExpr: {v.column}")

    # Only Hidden/AggOnly SelectExpr violations can be rewritten
    select_violations = [v for v in violations if v.role == "SelectExpr"]
    if not select_violations:
        # Other violations that weren't handled above
        return RewriteResult(True, sql=query)

    # Apply rewrites (max 2 steps)
    current_query = query
    for _ in range(2):
        current_query, remaining = _apply_rewrite_step(
            current_query, select_violations, schema, policies
        )
        if not remaining:
            return RewriteResult(True, sql=current_query)
        select_violations = remaining

    return RewriteResult(False, reason="Rewrite limit exceeded")


def _apply_rewrite_step(
    query: str,
    violations: list[Violation],
    schema: TableSchema,
    policies: dict[str, PolicyType],
) -> tuple[str, list[Violation]]:
    """Apply one step of rewriting."""
    remaining: list[Violation] = []

    for v in violations:
        if v.policy == "Hidden":
            # R1: Replace Hidden column with Public *_id column
            replacement = _find_id_column(v.column, schema, policies)
            if replacement:
                query = _replace_column(query, v.column, replacement)
            else:
                remaining.append(v)

        elif v.policy == "AggOnly":
            # R2: Wrap with AVG()
            col_name = v.column.split(".")[-1]
            new_query = _wrap_with_avg(query, col_name)
            if new_query != query:
                query = new_query
            else:
                remaining.append(v)

    return query, remaining


def _find_id_column(
    column: str, schema: TableSchema, policies: dict[str, PolicyType]
) -> str | None:
    """Find a Public *_id column in the same table (prefer PK).

    Only Public columns can be used as replacements since they're allowed in SelectExpr.
    JoinOnly columns cannot be used because they would still violate policy in SelectExpr.
    """
    table = column.split(".")[0]
    table_lower = table.lower()
    candidates: list[tuple[bool, int, str]] = []

    # ID column patterns (matching policy_assigner.py priority 1 rules)
    id_patterns = [
        re.compile(r"^id$", re.I),
        re.compile(r"_id$", re.I),
        re.compile(r"^id_", re.I),
        re.compile(r"_code$", re.I),
        re.compile(r"^stuid$", re.I),
    ]

    def is_id_column(name: str) -> bool:
        return any(p.search(name) for p in id_patterns)

    # Build column map for the table
    for col_id, (table_idx, col_name) in enumerate(schema.column_names):
        if col_id == 0:  # Skip "*"
            continue
        if table_idx < 0:
            continue
        if schema.table_names[table_idx].lower() != table_lower:
            continue

        full_name = f"{schema.table_names[table_idx]}.{col_name}"

        # Only Public columns can be used in SelectExpr
        if is_id_column(col_name) and policies.get(full_name) == "Public":
            is_pk = col_id in schema.primary_keys
            candidates.append((is_pk, col_id, full_name))

    if not candidates:
        return None

    # Sort: PK first, then by col_id
    candidates.sort(key=lambda x: (not x[0], x[1]))
    return candidates[0][2]


def _replace_column(query: str, old_col: str, new_col: str) -> str:
    """Replace column name in SQL string."""
    old_name = old_col.split(".")[-1]
    new_name = new_col.split(".")[-1]

    # Case-insensitive word boundary replacement
    pattern = rf"\b{re.escape(old_name)}\b"
    return re.sub(pattern, new_name, query, flags=re.IGNORECASE)


def _wrap_with_avg(query: str, col_name: str) -> str:
    """Wrap a column with AVG() in SELECT clause."""
    # Match SELECT ... col_name ... FROM
    # Replace col_name with AVG(col_name) if it's not already in an aggregate

    # Simple approach: find col_name after SELECT and before FROM
    select_match = re.search(r"\bSELECT\b(.+?)\bFROM\b", query, re.IGNORECASE | re.DOTALL)
    if not select_match:
        return query

    select_part = select_match.group(1)

    # Check if col_name is already wrapped in an aggregate
    # Pattern: aggregates like AVG(...col_name...), COUNT(...), etc.
    agg_pattern = rf"\b(AVG|COUNT|SUM|MAX|MIN)\s*\([^)]*\b{re.escape(col_name)}\b[^)]*\)"
    if re.search(agg_pattern, select_part, re.IGNORECASE):
        return query  # Already aggregated

    # Replace bare col_name with AVG(col_name)
    # Match: (possibly T.) col_name that's not part of an aggregate
    pattern = rf"(\b(?:\w+\.)?)({re.escape(col_name)})\b"

    def replacer(m: re.Match) -> str:
        prefix = m.group(1)  # Table alias prefix if any
        return f"AVG({prefix}{col_name})"

    new_select = re.sub(pattern, replacer, select_part, flags=re.IGNORECASE)

    if new_select == select_part:
        return query  # No replacement made

    return query[: select_match.start(1)] + new_select + query[select_match.end(1) :]
