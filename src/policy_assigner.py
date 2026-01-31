"""Policy assignment for database columns."""

import json
import re
from pathlib import Path

from .types import PolicyType, TableSchema

# Policy rules with priority (lower number = higher priority)
# Format: (priority, pattern, policy)
POLICY_RULES: list[tuple[int, re.Pattern[str], PolicyType]] = [
    # Priority 1: ID columns -> JoinOnly
    (1, re.compile(r"^id$", re.I), "JoinOnly"),
    (1, re.compile(r"_id$", re.I), "JoinOnly"),
    (1, re.compile(r"^id_", re.I), "JoinOnly"),
    (1, re.compile(r"_code$", re.I), "JoinOnly"),
    (1, re.compile(r"^stuid$", re.I), "JoinOnly"),
    # Priority 2: PII -> Hidden (contains patterns)
    (2, re.compile(r"email", re.I), "Hidden"),
    (2, re.compile(r"phone", re.I), "Hidden"),
    (2, re.compile(r"address", re.I), "Hidden"),
    (2, re.compile(r"gender", re.I), "Hidden"),
    (2, re.compile(r"nationality", re.I), "Hidden"),
    (2, re.compile(r"birth", re.I), "Hidden"),
    (2, re.compile(r"ssn", re.I), "Hidden"),
    (2, re.compile(r"password", re.I), "Hidden"),
    # Priority 2: PII -> Hidden (exact match patterns)
    (2, re.compile(r"^sex$", re.I), "Hidden"),
    (2, re.compile(r"^weight$", re.I), "Hidden"),
    (2, re.compile(r"^height$", re.I), "Hidden"),
    (2, re.compile(r"^age$", re.I), "Hidden"),
    # Priority 3: Financial/Score -> AggOnly (contains patterns)
    (3, re.compile(r"salary", re.I), "AggOnly"),
    (3, re.compile(r"income", re.I), "AggOnly"),
    (3, re.compile(r"price", re.I), "AggOnly"),
    (3, re.compile(r"amount", re.I), "AggOnly"),
    (3, re.compile(r"cost", re.I), "AggOnly"),
    (3, re.compile(r"budget", re.I), "AggOnly"),
    (3, re.compile(r"balance", re.I), "AggOnly"),
    (3, re.compile(r"revenue", re.I), "AggOnly"),
    (3, re.compile(r"profit", re.I), "AggOnly"),
    (3, re.compile(r"score", re.I), "AggOnly"),
    (3, re.compile(r"rating", re.I), "AggOnly"),
    # Priority 3: Financial/Score -> AggOnly (exact match patterns)
    (3, re.compile(r"^total$", re.I), "AggOnly"),
]


def assign_policy(column_name: str) -> PolicyType:
    """Determine policy for a column based on its name."""
    for _, pattern, policy in POLICY_RULES:
        if pattern.search(column_name):
            return policy
    return "Public"


def assign_policies_for_db(schema: TableSchema) -> dict[str, PolicyType]:
    """Assign policies to all columns in a database."""
    policies: dict[str, PolicyType] = {}

    for col_id in range(1, len(schema.column_names)):  # Skip col_id=0 (*)
        table_idx, col_name = schema.column_names[col_id]
        if table_idx < 0:
            continue
        table_name = schema.table_names[table_idx]
        full_name = f"{table_name}.{col_name}"
        policies[full_name] = assign_policy(col_name)

    return policies


def load_overrides(overrides_path: str | Path) -> list[dict]:
    """Load override file if it exists."""
    path = Path(overrides_path)
    if not path.exists():
        return []
    with open(path) as f:
        return json.load(f)


def apply_overrides(
    policies: dict[str, PolicyType], overrides: list[dict], db_id: str
) -> dict[str, PolicyType]:
    """Apply manual overrides to policies."""
    for ov in overrides:
        if ov["db_id"] == db_id:
            key = f"{ov['table']}.{ov['column']}"
            if key in policies:
                policies[key] = ov["final_policy"]
    return policies


def generate_all_policies(
    schemas: dict[str, TableSchema],
    output_dir: str | Path,
    overrides_path: str | Path | None = None,
) -> dict[str, dict[str, PolicyType]]:
    """Generate policy files for all databases."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    overrides = load_overrides(overrides_path) if overrides_path else []

    all_policies: dict[str, dict[str, PolicyType]] = {}

    for db_id, schema in schemas.items():
        policies = assign_policies_for_db(schema)
        policies = apply_overrides(policies, overrides, db_id)
        all_policies[db_id] = policies

        # Write to file
        output_file = output_dir / f"{db_id}.json"
        with open(output_file, "w") as f:
            json.dump({"db_id": db_id, "policies": policies}, f, indent=2)

    return all_policies


def print_policy_stats(schemas: dict[str, TableSchema], policies: dict[str, dict[str, PolicyType]]):
    """Print policy distribution statistics."""
    stats = {"Public": 0, "JoinOnly": 0, "AggOnly": 0, "Hidden": 0}
    tables_with_hidden = 0
    tables_with_aggonly = 0
    total_tables = 0
    dbs_with_sensitive = 0

    for db_id, db_policies in policies.items():
        for policy in db_policies.values():
            stats[policy] += 1

        table_policies: dict[str, set[PolicyType]] = {}
        for col_name, policy in db_policies.items():
            table = col_name.split(".")[0]
            if table not in table_policies:
                table_policies[table] = set()
            table_policies[table].add(policy)

        for table_pols in table_policies.values():
            total_tables += 1
            if "Hidden" in table_pols:
                tables_with_hidden += 1
            if "AggOnly" in table_pols:
                tables_with_aggonly += 1

        db_has_sensitive = any(p in ("Hidden", "AggOnly") for p in db_policies.values())
        if db_has_sensitive:
            dbs_with_sensitive += 1

    total = sum(stats.values())
    print("\nPolicy Distribution:")
    for policy, count in stats.items():
        pct = count / total * 100 if total > 0 else 0
        print(f"  {policy:10s}: {count:4d} ({pct:5.1f}%)")

    print("\nTable/DB Coverage:")
    if total_tables > 0:
        print(f"  Tables with Hidden:  {tables_with_hidden / total_tables * 100:.1f}%")
        print(f"  Tables with AggOnly: {tables_with_aggonly / total_tables * 100:.1f}%")
    print(f"  DBs with Hidden or AggOnly: {dbs_with_sensitive / len(policies) * 100:.1f}%")
