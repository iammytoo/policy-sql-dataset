"""Core type definitions for Policy SQL Dataset."""

from dataclasses import dataclass, field
from typing import Any, Literal

PolicyType = Literal["Public", "JoinOnly", "AggOnly", "Hidden"]
RoleType = Literal["SelectExpr", "JoinCond", "WherePred", "AggArg"]
GoldLabelType = Literal["SQL", "REFUSE"]


@dataclass
class ColumnRef:
    """A column reference extracted from SQL AST."""

    table: str
    column: str
    role: RoleType
    agg_id: int  # 0=none, 1=max, 2=min, 3=count, 4=sum, 5=avg


@dataclass
class Violation:
    """A policy violation detected in SQL."""

    column: str  # "table.column" format
    role: RoleType
    policy: PolicyType
    agg_id: int


@dataclass
class GoldLabel:
    """Gold label for evaluation (SQL or REFUSE)."""

    type: GoldLabelType
    sql: str | None = None


@dataclass
class NegativeExample:
    """A synthetic negative example with intentional policy violations."""

    sql: str
    violations: list[Violation] = field(default_factory=list)


@dataclass
class TableSchema:
    """Schema information for a database table."""

    db_id: str
    table_names: list[str]  # Original table names
    column_names: list[tuple[int, str]]  # (table_idx, column_name), -1 for "*"
    column_types: list[str]
    primary_keys: list[int]  # Column indices that are PKs
    foreign_keys: list[tuple[int, int]]  # (from_col_idx, to_col_idx)

    def resolve_column(self, col_id: int) -> str:
        """Resolve col_id to 'table.column' format."""
        if col_id == 0:
            return "*"
        table_idx, col_name = self.column_names[col_id]
        if table_idx < 0:
            return col_name
        table_name = self.table_names[table_idx]
        return f"{table_name}.{col_name}"


@dataclass
class SpiderExample:
    """A single example from Spider dataset."""

    db_id: str
    question: str
    query: str
    sql: dict[str, Any]  # Parsed AST from Spider


@dataclass
class ProcessedExample:
    """Fully processed example with policy analysis."""

    id: str
    db_id: str
    question: str
    original_sql: str
    column_policies: dict[str, PolicyType]  # "table.column" -> PolicyType
    violations_original: list[Violation]
    gold_label: GoldLabel
    negative_examples: list[NegativeExample]
