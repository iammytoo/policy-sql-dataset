# Step 08: Negative Example 生成

## 目的

明示的な policy 違反 SQL を生成し、評価を強化する。

## 入力

- `SpiderExample`
- `policies`
- `schema`

## 出力

```python
list[NegativeExample]  # 最大1件
```

## タスク

- [ ] N1: Hidden 列を SELECT に追加
- [ ] N2: AggOnly の集計を剥がす
- [ ] N3: JoinOnly 列を SELECT に追加
- [ ] 優先順位に従い1件生成
- [ ] 生成した SQL の violation を再計算

## 実装: negative_generator.py

```python
def generate_negative(
    example: SpiderExample,
    policies: dict[str, PolicyType],
    schema: TableSchema
) -> list[NegativeExample]:
    """Negative Example を生成（最大1件）"""

    # N1: Hidden 列を追加
    negative = _try_add_hidden(example, policies, schema)
    if negative:
        return [negative]

    # N2: AggOnly の集計を剥がす
    negative = _try_unwrap_agg(example, policies, schema)
    if negative:
        return [negative]

    # N3: JoinOnly 列を追加
    negative = _try_add_joinonly(example, policies, schema)
    if negative:
        return [negative]

    return []

def _try_add_hidden(
    example: SpiderExample,
    policies: dict[str, PolicyType],
    schema: TableSchema
) -> NegativeExample | None:
    """SELECT に Hidden 列を追加"""
    # 使用中のテーブルから Hidden 列を探す
    tables = _extract_tables(example.sql, schema)

    for table in tables:
        for col_key, policy in policies.items():
            if policy == "Hidden" and col_key.startswith(f"{table}."):
                col_name = col_key.split(".")[-1]
                new_sql = _add_to_select(example.query, col_name)
                # 追加した列の違反を直接構築
                violations = _compute_violations_for_added_column(col_key, policy)
                return NegativeExample(sql=new_sql, violations=violations)

    return None

def _try_unwrap_agg(
    example: SpiderExample,
    policies: dict[str, PolicyType],
    schema: TableSchema
) -> NegativeExample | None:
    """集計関数を剥がして AggOnly 違反を作る"""
    # AVG(col) → col のパターンを探す
    import re

    for col_key, policy in policies.items():
        if policy != "AggOnly":
            continue
        col_name = col_key.split(".")[-1]

        # AVG(col) または COUNT(col) を探す
        pattern = rf'\b(AVG|COUNT)\s*\(\s*{col_name}\s*\)'
        if re.search(pattern, example.query, re.IGNORECASE):
            new_sql = re.sub(pattern, col_name, example.query, flags=re.IGNORECASE)
            # 集計を剥がした列の違反を構築
            violations = _compute_violations_for_unwrapped_agg(col_key, policy)
            return NegativeExample(sql=new_sql, violations=violations)

    return None

def _try_add_joinonly(
    example: SpiderExample,
    policies: dict[str, PolicyType],
    schema: TableSchema
) -> NegativeExample | None:
    """SELECT に JoinOnly 列を追加"""
    tables = _extract_tables(example.sql, schema)

    for table in tables:
        for col_key, policy in policies.items():
            if policy == "JoinOnly" and col_key.startswith(f"{table}."):
                # 既に SELECT にある場合はスキップ
                col_name = col_key.split(".")[-1]
                if col_name.lower() in example.query.lower():
                    continue
                new_sql = _add_to_select(example.query, col_name)
                # 追加した列の違反を直接構築
                violations = _compute_violations_for_added_column(col_key, policy)
                if violations:  # 違反がある場合のみ
                    return NegativeExample(sql=new_sql, violations=violations)

    return None

def _add_to_select(query: str, col_name: str) -> str:
    """SELECT 句に列を追加"""
    import re
    # SELECT x, y → SELECT col_name, x, y
    return re.sub(
        r'\bSELECT\s+',
        f'SELECT {col_name}, ',
        query,
        count=1,
        flags=re.IGNORECASE
    )

def _extract_tables(sql: dict, schema: TableSchema) -> list[str]:
    """FROM 句からテーブル名を抽出"""
    tables = []
    for table_unit in sql["from"]["table_units"]:
        if table_unit[0] == "table_unit":
            # table_unit[1] は テーブルのインデックス（整数）
            table_idx = table_unit[1]
            # schema.tables[table_idx] でテーブル名を取得
            if 0 <= table_idx < len(schema.tables):
                tables.append(schema.tables[table_idx])
    return tables

def _compute_violations_for_added_column(
    col_key: str,
    policy: PolicyType
) -> list[Violation]:
    """追加した列の違反を直接構築（再パース不要）

    注: spec では「violation 検出器で再計算」とあったが、
    Negative 生成は編集距離1の変換であり、変換ごとに violation が論理的に確定する:
    - N1/N3: SELECT に列追加 → role=SelectExpr, agg_id=0
    - N2: 集計を剥がす → role=SelectExpr, agg_id=0
    再パースは不要であり、Spider パーサ不要の方針と整合する。

    Negative 生成では列を SELECT に追加するため、
    role は必ず SelectExpr になる。
    """
    # SELECT に追加した列は SelectExpr として扱う
    # Hidden/JoinOnly/AggOnly はすべて SelectExpr で違反
    if policy in ("Hidden", "JoinOnly", "AggOnly"):
        return [Violation(
            column=col_key,
            role="SelectExpr",
            policy=policy,
            agg_id=0
        )]
    return []

def _compute_violations_for_unwrapped_agg(
    col_key: str,
    policy: PolicyType
) -> list[Violation]:
    """集計を剥がした列の違反を構築

    AVG(col) → col に変換した場合、
    col は SelectExpr（集計なし）として扱う。
    """
    if policy == "AggOnly":
        return [Violation(
            column=col_key,
            role="SelectExpr",
            policy=policy,
            agg_id=0  # 集計なし
        )]
    return []
```

## 注意点

### 違反の計算

Negative 生成では、追加・変更した列の違反を直接構築する（再パース不要）。

- N1/N3: 列を SELECT に追加 → role は必ず `SelectExpr`
- N2: 集計を剥がす → role は `SelectExpr`（集計なし）

この方法なら Spider パーサ不要で、かつ正確に違反を計算できる。

### テーブル名の解決

`sql["from"]["table_units"]` の `table_unit[1]` は**整数インデックス**。
`schema.tables[table_idx]` でテーブル名に解決する必要がある。

### 編集距離

全ての negative は **編集距離 1**（1箇所の変更）とする。

## テストケース

```python
def test_add_hidden():
    example = SpiderExample(query="SELECT name FROM users", ...)
    policies = {"users.email": "Hidden", "users.name": "Public"}
    negatives = generate_negative(example, policies, schema)
    assert len(negatives) == 1
    assert "email" in negatives[0].sql

def test_unwrap_agg():
    example = SpiderExample(query="SELECT AVG(salary) FROM employees", ...)
    policies = {"employees.salary": "AggOnly"}
    negatives = generate_negative(example, policies, schema)
    assert len(negatives) == 1
    assert "AVG" not in negatives[0].sql
    assert "salary" in negatives[0].sql
```

## 完了条件

- N1/N2/N3 が優先順位通りに動作する
- 生成される negative は最大1件
- 違反が正しく計算される
