# Step 03: Policy 自動付与

## 目的

各DBの各列に Policy を自動付与し、DB別の policy ファイルを生成する。

## 入力

- `TableSchema`（Step 02 で生成）

## 出力

```
data/policies/
├── concert_singer.json
├── perpetrator.json
└── ...
```

## タスク

- [ ] 列名パターンマッチによる Policy 判定
- [ ] 優先順位に基づく判定ロジック
- [ ] override ファイルの適用（存在すれば）
- [ ] DB別 policy JSON の出力

## 実装: policy_assigner.py

```python
import re

POLICY_RULES = [
    # 優先度1: ID系 → JoinOnly
    (1, re.compile(r'^id$', re.I), "JoinOnly"),
    (1, re.compile(r'_id$', re.I), "JoinOnly"),
    (1, re.compile(r'^id_', re.I), "JoinOnly"),
    (1, re.compile(r'_code$', re.I), "JoinOnly"),
    (1, re.compile(r'^stuid$', re.I), "JoinOnly"),

    # 優先度2: 個人情報 → Hidden（「含む」パターン）
    (2, re.compile(r'email', re.I), "Hidden"),
    (2, re.compile(r'phone', re.I), "Hidden"),
    (2, re.compile(r'address', re.I), "Hidden"),
    (2, re.compile(r'gender', re.I), "Hidden"),
    (2, re.compile(r'nationality', re.I), "Hidden"),
    (2, re.compile(r'birth', re.I), "Hidden"),
    (2, re.compile(r'ssn', re.I), "Hidden"),
    (2, re.compile(r'password', re.I), "Hidden"),
    # 優先度2: 個人情報 → Hidden（「完全一致」パターン）
    (2, re.compile(r'^sex$', re.I), "Hidden"),
    (2, re.compile(r'^weight$', re.I), "Hidden"),
    (2, re.compile(r'^height$', re.I), "Hidden"),
    (2, re.compile(r'^age$', re.I), "Hidden"),

    # 優先度3: 金額・スコア → AggOnly（「含む」パターン）
    (3, re.compile(r'salary', re.I), "AggOnly"),
    (3, re.compile(r'income', re.I), "AggOnly"),
    (3, re.compile(r'price', re.I), "AggOnly"),
    (3, re.compile(r'amount', re.I), "AggOnly"),
    (3, re.compile(r'cost', re.I), "AggOnly"),
    (3, re.compile(r'budget', re.I), "AggOnly"),
    (3, re.compile(r'balance', re.I), "AggOnly"),
    (3, re.compile(r'revenue', re.I), "AggOnly"),
    (3, re.compile(r'profit', re.I), "AggOnly"),
    (3, re.compile(r'score', re.I), "AggOnly"),
    (3, re.compile(r'rating', re.I), "AggOnly"),
    # 優先度3: 金額・スコア → AggOnly（「完全一致」パターン）
    (3, re.compile(r'^total$', re.I), "AggOnly"),
]

def assign_policy(column_name: str) -> PolicyType:
    """列名から Policy を判定"""
    for _, pattern, policy in POLICY_RULES:
        if pattern.search(column_name):
            return policy
    return "Public"

def assign_policies_for_db(schema: TableSchema) -> dict[str, PolicyType]:
    """DB内の全列に Policy を付与"""
    policies = {}
    for col_id, full_name in schema.columns.items():
        if full_name == "*":
            continue
        _, col_name = full_name.split(".", 1)
        policies[full_name] = assign_policy(col_name)
    return policies

def apply_overrides(
    policies: dict[str, PolicyType],
    overrides: list[dict],
    db_id: str
) -> dict[str, PolicyType]:
    """override ファイルを適用"""
    for ov in overrides:
        if ov["db_id"] == db_id:
            key = f"{ov['table']}.{ov['column']}"
            if key in policies:
                policies[key] = ov["final_policy"]
    return policies
```

## 出力フォーマット

```json
{
  "db_id": "concert_singer",
  "policies": {
    "stadium.stadium_id": "JoinOnly",
    "stadium.name": "Public",
    "singer.salary": "AggOnly"
  }
}
```

## 統計出力

生成時に以下の統計を出力する：

```
Policy 分布:
  Public:   2844 (63.2%)
  JoinOnly: 1265 (28.1%)
  AggOnly:   122 ( 2.7%)
  Hidden:    272 ( 6.0%)

テーブル/DB カバレッジ:
  Hidden 列を含むテーブル:  17.1%
  AggOnly 列を含むテーブル: 11.3%
  Hidden or AggOnly を含む DB: 76.5%
```

## 完了条件

- 全 166 DB の policy ファイルが生成される
- 優先順位が正しく機能する（`address_id` → JoinOnly）
- 統計が仕様の期待値と大きく乖離しない
