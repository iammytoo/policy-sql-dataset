"""Violation detection for policy compliance."""

from .types import ColumnRef, PolicyType, RoleType, Violation

# Policy × Role permission table
PERMISSION_TABLE: dict[PolicyType, dict[RoleType, bool]] = {
    "Public": {
        "SelectExpr": True,
        "JoinCond": True,
        "WherePred": True,
        "AggArg": True,
    },
    "JoinOnly": {
        "SelectExpr": False,
        "JoinCond": True,
        "WherePred": True,
        "AggArg": False,
    },
    "AggOnly": {
        "SelectExpr": False,
        "JoinCond": False,
        "WherePred": False,
        "AggArg": True,  # Only AVG/COUNT allowed
    },
    "Hidden": {
        "SelectExpr": False,
        "JoinCond": False,
        "WherePred": False,
        "AggArg": False,
    },
}

# agg_ids allowed for AggOnly columns
AGGONLY_ALLOWED_AGGS = {3, 5}  # count=3, avg=5


def is_allowed(policy: PolicyType, role: RoleType, agg_id: int) -> bool:
    """Check if a column usage is allowed given its policy and role."""
    # Base permission check
    if not PERMISSION_TABLE[policy][role]:
        return False

    # AggOnly special check: only AVG/COUNT are permitted
    if policy == "AggOnly" and role == "AggArg":
        if agg_id not in AGGONLY_ALLOWED_AGGS:
            return False

    return True


def check_violations(
    refs: list[ColumnRef], policies: dict[str, PolicyType]
) -> list[Violation]:
    """Detect violations from column references against policies."""
    violations: list[Violation] = []

    for ref in refs:
        col_key = f"{ref.table}.{ref.column}"
        policy = policies.get(col_key, "Public")

        if not is_allowed(policy, ref.role, ref.agg_id):
            violations.append(
                Violation(
                    column=col_key,
                    role=ref.role,
                    policy=policy,
                    agg_id=ref.agg_id,
                )
            )

    return violations
