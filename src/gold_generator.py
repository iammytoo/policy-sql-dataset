"""Gold label generation for evaluation."""

from .rewriter import RewriteResult
from .role_extractor import has_select_star
from .types import GoldLabel, SpiderExample, Violation


def generate_gold_label(
    example: SpiderExample,
    violations: list[Violation],
    rewrite_result: RewriteResult | None,
) -> GoldLabel:
    """Generate gold label (SQL or REFUSE) for an example."""
    # SELECT * check (except COUNT(*) etc.)
    if has_select_star(example.sql):
        return GoldLabel(type="REFUSE", sql=None)

    # No violations -> original SQL
    if not violations:
        return GoldLabel(type="SQL", sql=example.query)

    # Rewrite succeeded -> rewritten SQL
    if rewrite_result and rewrite_result.success:
        return GoldLabel(type="SQL", sql=rewrite_result.sql)

    # Rewrite failed or not attempted -> REFUSE
    return GoldLabel(type="REFUSE", sql=None)
