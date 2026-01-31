# Step 09: 出力生成

## 目的

全処理結果を最終的な JSON ファイルとして出力する。

## 入力

- 全ての処理結果（Step 02-08）

## 出力

```
data/
├── train.json
├── dev.json
├── test.json
└── policies/
    ├── concert_singer.json
    └── ...
```

## タスク

- [ ] 出力レコード構造の組み立て
- [ ] train/dev/test 別に出力
- [ ] 進捗表示
- [ ] 出力統計の表示

## 実装: output_writer.py

```python
import json
from pathlib import Path
from tqdm import tqdm

@dataclass
class OutputRecord:
    id: str
    db_id: str
    question: str
    original_sql: str
    column_policies: dict[str, str]
    violations_original: list[dict]
    gold_label: dict
    negative_examples: list[dict]

def write_dataset(
    records: list[OutputRecord],
    output_path: Path,
    split: str
) -> None:
    """データセットを JSON として出力"""
    output_file = output_path / f"{split}.json"

    data = []
    for record in tqdm(records, desc=f"Writing {split}"):
        data.append({
            "id": record.id,
            "db_id": record.db_id,
            "question": record.question,
            "original_sql": record.original_sql,
            "column_policies": record.column_policies,
            "violations_original": [
                {
                    "column": v.column,
                    "role": v.role,
                    "policy": v.policy,
                    "agg_id": v.agg_id
                }
                for v in record.violations_original
            ],
            "gold_label": {
                "type": record.gold_label.type,
                "sql": record.gold_label.sql
            },
            "negative_examples": [
                {
                    "sql": neg.sql,
                    "violations": [
                        {
                            "column": v.column,
                            "role": v.role,
                            "policy": v.policy,
                            "agg_id": v.agg_id
                        }
                        for v in neg.violations
                    ]
                }
                for neg in record.negative_examples
            ]
        })

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"Wrote {len(data)} records to {output_file}")

def write_policies(
    all_policies: dict[str, dict[str, str]],
    output_path: Path
) -> None:
    """DB別 policy ファイルを出力"""
    policies_dir = output_path / "policies"
    policies_dir.mkdir(exist_ok=True)

    for db_id, policies in all_policies.items():
        policy_file = policies_dir / f"{db_id}.json"
        with open(policy_file, "w", encoding="utf-8") as f:
            json.dump({
                "db_id": db_id,
                "policies": policies
            }, f, indent=2, ensure_ascii=False)

    print(f"Wrote {len(all_policies)} policy files to {policies_dir}")
```

## 出力フォーマット（1レコード）

```json
{
  "id": "train_0001",
  "db_id": "concert_singer",
  "question": "How many singers do we have?",
  "original_sql": "SELECT count(*) FROM singer",
  "column_policies": {
    "singer.singer_id": "JoinOnly",
    "singer.name": "Public",
    "singer.salary": "AggOnly"
  },
  "violations_original": [],
  "gold_label": {
    "type": "SQL",
    "sql": "SELECT count(*) FROM singer"
  },
  "negative_examples": [
    {
      "sql": "SELECT salary FROM singer",
      "violations": [
        {
          "column": "singer.salary",
          "role": "SelectExpr",
          "policy": "AggOnly",
          "agg_id": 0
        }
      ]
    }
  ]
}
```

## 出力統計

書き込み後に以下を表示：

```
=== Output Statistics ===
Split: train
  Total records: 7000
  With violations: 1200 (17.1%)
  Gold SQL: 6200 (88.6%)
  Gold REFUSE: 800 (11.4%)
  With negative: 5500 (78.6%)
```

## 完了条件

- train/dev/test の全ファイルが正しく出力される
- JSON が valid である
- 統計が仕様の期待値と大きく乖離しない
