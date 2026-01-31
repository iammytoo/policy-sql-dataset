# Step 10: QA チェック

## 目的

生成されたデータセットの品質を検証し、異常を検知する。

## 入力

- `data/train.json`
- `data/dev.json`
- `data/test.json`

## 出力

- QA レポート（標準出力 + `data/qa_report.json`）

## タスク

- [ ] Q1: violation 率の計算
- [ ] Q2: REFUSE 率の計算
- [ ] Q3: DB別偏りの検出
- [ ] Q4: negative edit distance の検証
- [ ] Q5: role別 violation 分布
- [ ] 異常値のアラート

## 実装: qa_checker.py

```python
import json
from pathlib import Path
from collections import Counter, defaultdict
import statistics

@dataclass
class QAReport:
    split: str
    total_records: int
    violation_rate: float
    refuse_rate: float
    negative_rate: float
    role_distribution: dict[str, int]
    policy_distribution: dict[str, int]
    db_refuse_rates: dict[str, float]
    warnings: list[str]

def run_qa_check(data_path: Path, split: str) -> QAReport:
    """QA チェックを実行"""
    with open(data_path / f"{split}.json") as f:
        data = json.load(f)

    warnings = []

    # Q1: violation 率
    with_violations = sum(1 for r in data if r["violations_original"])
    violation_rate = with_violations / len(data)

    if violation_rate < 0.05 or violation_rate > 0.40:
        warnings.append(f"Q1: Unusual violation rate: {violation_rate:.1%}")

    # Q2: REFUSE 率
    refuse_count = sum(1 for r in data if r["gold_label"]["type"] == "REFUSE")
    refuse_rate = refuse_count / len(data)

    if refuse_rate < 0.02 or refuse_rate > 0.25:
        warnings.append(f"Q2: Unusual REFUSE rate: {refuse_rate:.1%}")

    # Q3: DB別 REFUSE 率の偏り
    db_refuse = defaultdict(lambda: {"total": 0, "refuse": 0})
    for r in data:
        db_refuse[r["db_id"]]["total"] += 1
        if r["gold_label"]["type"] == "REFUSE":
            db_refuse[r["db_id"]]["refuse"] += 1

    db_refuse_rates = {
        db: d["refuse"] / d["total"] if d["total"] > 0 else 0
        for db, d in db_refuse.items()
    }

    rates = list(db_refuse_rates.values())
    if rates:
        std_dev = statistics.stdev(rates) if len(rates) > 1 else 0
        if std_dev > 0.3:
            warnings.append(f"Q3: High DB REFUSE rate variance: stdev={std_dev:.2f}")

    # Q4: negative edit distance（簡易チェック）
    negative_rate = sum(1 for r in data if r["negative_examples"]) / len(data)

    # Q5: role別 violation 分布
    role_counter = Counter()
    policy_counter = Counter()
    for r in data:
        for v in r["violations_original"]:
            role_counter[v["role"]] += 1
            policy_counter[v["policy"]] += 1

    # JoinCond が極端に少ないかチェック
    if role_counter and role_counter.get("JoinCond", 0) < role_counter.total() * 0.05:
        warnings.append("Q5: JoinCond violations are very rare")

    return QAReport(
        split=split,
        total_records=len(data),
        violation_rate=violation_rate,
        refuse_rate=refuse_rate,
        negative_rate=negative_rate,
        role_distribution=dict(role_counter),
        policy_distribution=dict(policy_counter),
        db_refuse_rates=db_refuse_rates,
        warnings=warnings
    )

def print_qa_report(report: QAReport) -> None:
    """QA レポートを表示"""
    print(f"\n{'='*50}")
    print(f"QA Report: {report.split}")
    print(f"{'='*50}")
    print(f"Total records: {report.total_records}")
    print(f"Violation rate: {report.violation_rate:.1%}")
    print(f"REFUSE rate: {report.refuse_rate:.1%}")
    print(f"Negative rate: {report.negative_rate:.1%}")
    print()
    print("Role distribution:")
    for role, count in sorted(report.role_distribution.items()):
        print(f"  {role}: {count}")
    print()
    print("Policy distribution:")
    for policy, count in sorted(report.policy_distribution.items()):
        print(f"  {policy}: {count}")

    if report.warnings:
        print()
        print("WARNINGS:")
        for w in report.warnings:
            print(f"  ⚠ {w}")

def save_qa_report(reports: list[QAReport], output_path: Path) -> None:
    """QA レポートを JSON として保存"""
    data = []
    for r in reports:
        data.append({
            "split": r.split,
            "total_records": r.total_records,
            "violation_rate": r.violation_rate,
            "refuse_rate": r.refuse_rate,
            "negative_rate": r.negative_rate,
            "role_distribution": r.role_distribution,
            "policy_distribution": r.policy_distribution,
            "warnings": r.warnings
        })

    with open(output_path / "qa_report.json", "w") as f:
        json.dump(data, f, indent=2)
```

## 期待値と閾値

| 指標 | 期待範囲 | アラート条件 |
|------|----------|--------------|
| Q1: violation 率 | 10-30% | <5% or >40% |
| Q2: REFUSE 率 | 5-15% | <2% or >25% |
| Q3: DB別 REFUSE stdev | <0.2 | >0.3 |
| Q5: JoinCond 割合 | >5% | <5% |

## 出力例

```
==================================================
QA Report: dev
==================================================
Total records: 1034
Violation rate: 18.3%
REFUSE rate: 8.7%
Negative rate: 72.4%

Role distribution:
  AggArg: 45
  JoinCond: 23
  SelectExpr: 156
  WherePred: 34

Policy distribution:
  AggOnly: 45
  Hidden: 89
  JoinOnly: 124

WARNINGS:
  (none)
```

## 完了条件

- 全 split の QA チェックが実行される
- 異常時に warning が出力される
- レポートが JSON で保存される
