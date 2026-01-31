"""Quality assurance checker for generated dataset."""

import json
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class QAReport:
    """QA check report."""

    split: str
    total_records: int
    violation_rate: float
    refuse_rate: float
    negative_rate: float
    role_distribution: dict[str, int] = field(default_factory=dict)
    policy_distribution: dict[str, int] = field(default_factory=dict)
    db_refuse_rates: dict[str, float] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


def run_qa_check(data_path: Path, split: str) -> QAReport:
    """Run QA checks on dataset."""
    with open(data_path / f"{split}.json") as f:
        data = json.load(f)

    if not data:
        return QAReport(
            split=split,
            total_records=0,
            violation_rate=0,
            refuse_rate=0,
            negative_rate=0,
            warnings=["No data found"],
        )

    warnings: list[str] = []

    # Q1: violation rate
    with_violations = sum(1 for r in data if r["violations_original"])
    violation_rate = with_violations / len(data)

    if violation_rate < 0.10:
        warnings.append(f"Q1: Violation rate too low: {violation_rate:.1%} (expected >10%)")
    elif violation_rate > 0.30:
        warnings.append(f"Q1: Violation rate too high: {violation_rate:.1%} (expected <30%)")

    # Q2: REFUSE rate
    refuse_count = sum(1 for r in data if r["gold_label"]["type"] == "REFUSE")
    refuse_rate = refuse_count / len(data)

    if refuse_rate < 0.05:
        warnings.append(f"Q2: REFUSE rate too low: {refuse_rate:.1%} (expected >5%)")
    elif refuse_rate > 0.15:
        warnings.append(f"Q2: REFUSE rate too high: {refuse_rate:.1%} (expected <15%)")

    # Q3: DB-level REFUSE rate variance
    db_refuse: dict[str, dict[str, int]] = defaultdict(lambda: {"total": 0, "refuse": 0})
    for r in data:
        db_refuse[r["db_id"]]["total"] += 1
        if r["gold_label"]["type"] == "REFUSE":
            db_refuse[r["db_id"]]["refuse"] += 1

    db_refuse_rates = {
        db: d["refuse"] / d["total"] if d["total"] > 0 else 0 for db, d in db_refuse.items()
    }

    rates = list(db_refuse_rates.values())
    if len(rates) > 1:
        std_dev = statistics.stdev(rates)
        if std_dev > 0.3:
            warnings.append(
                f"Q3: High DB REFUSE rate variance: stdev={std_dev:.2f} (expected <0.3)"
            )

    # Q4: negative coverage and edit distance check
    negative_rate = sum(1 for r in data if r["negative_examples"]) / len(data)

    # Q4b: edit distance check (all negatives should have exactly 1 violation = edit distance 1)
    invalid_negatives = 0
    for r in data:
        for neg in r["negative_examples"]:
            if len(neg["violations"]) != 1:
                invalid_negatives += 1

    if invalid_negatives > 0:
        warnings.append(
            f"Q4: {invalid_negatives} negative examples with edit distance != 1"
        )

    # Q5: role distribution
    role_counter: Counter[str] = Counter()
    policy_counter: Counter[str] = Counter()
    for r in data:
        for v in r["violations_original"]:
            role_counter[v["role"]] += 1
            policy_counter[v["policy"]] += 1

    total_violations = role_counter.total()
    if total_violations > 0:
        joincond_ratio = role_counter.get("JoinCond", 0) / total_violations
        if joincond_ratio < 0.05:
            warnings.append(
                f"Q5: JoinCond violations very rare: {joincond_ratio:.1%} (expected >5%)"
            )

    return QAReport(
        split=split,
        total_records=len(data),
        violation_rate=violation_rate,
        refuse_rate=refuse_rate,
        negative_rate=negative_rate,
        role_distribution=dict(role_counter),
        policy_distribution=dict(policy_counter),
        db_refuse_rates=db_refuse_rates,
        warnings=warnings,
    )


def print_qa_report(report: QAReport) -> None:
    """Print QA report to stdout."""
    print(f"\n{'=' * 50}")
    print(f"QA Report: {report.split}")
    print(f"{'=' * 50}")
    print(f"Total records: {report.total_records}")
    print(f"Violation rate: {report.violation_rate:.1%}")
    print(f"REFUSE rate: {report.refuse_rate:.1%}")
    print(f"Negative rate: {report.negative_rate:.1%}")

    if report.role_distribution:
        print("\nRole distribution:")
        for role, count in sorted(report.role_distribution.items()):
            print(f"  {role}: {count}")

    if report.policy_distribution:
        print("\nPolicy distribution:")
        for policy, count in sorted(report.policy_distribution.items()):
            print(f"  {policy}: {count}")

    if report.warnings:
        print("\nWARNINGS:")
        for w in report.warnings:
            print(f"  ! {w}")
    else:
        print("\nNo warnings.")


def save_qa_report(reports: list[QAReport], output_path: Path) -> None:
    """Save QA reports to JSON."""
    data = []
    for r in reports:
        data.append(
            {
                "split": r.split,
                "total_records": r.total_records,
                "violation_rate": r.violation_rate,
                "refuse_rate": r.refuse_rate,
                "negative_rate": r.negative_rate,
                "role_distribution": r.role_distribution,
                "policy_distribution": r.policy_distribution,
                "warnings": r.warnings,
            }
        )

    with open(output_path / "qa_report.json", "w") as f:
        json.dump(data, f, indent=2)

    print(f"\nSaved QA report to {output_path / 'qa_report.json'}")
