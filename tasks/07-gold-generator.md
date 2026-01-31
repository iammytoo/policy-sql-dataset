# Step 07: Gold Label 生成

## 目的

各質問に対する Gold Label（SQL or REFUSE）を生成する。

## 入力

- `SpiderExample`（元データ）
- `violations`（Step 05）
- `RewriteResult`（Step 06）

## 出力

```python
GoldLabel:
  type: "SQL" | "REFUSE"
  sql: str | None
```

## タスク

- [ ] 違反なし → SQL(original)
- [ ] 違反あり + rewrite成功 → SQL(rewritten)
- [ ] 違反あり + rewrite失敗 → REFUSE
- [ ] SELECT * の検出 → REFUSE

## 実装: gold_generator.py

```python
def generate_gold_label(
    example: SpiderExample,
    violations: list[Violation],
    rewrite_result: RewriteResult | None
) -> GoldLabel:
    """Gold Label を生成"""

    # SELECT * チェック
    if _has_select_star(example.sql):
        return GoldLabel(type="REFUSE", sql=None)

    # 違反なし
    if not violations:
        return GoldLabel(type="SQL", sql=example.query)

    # rewrite 成功
    if rewrite_result and rewrite_result.success:
        return GoldLabel(type="SQL", sql=rewrite_result.sql)

    # rewrite 失敗 or 未実行
    return GoldLabel(type="REFUSE", sql=None)

def _has_select_star(sql: dict) -> bool:
    """SELECT * を含むかチェック（COUNT(*) は除く）"""
    is_distinct, val_units = sql["select"]
    for agg_id, val_unit in val_units:
        unit_op, col_unit1, col_unit2 = val_unit
        if col_unit1:
            inner_agg_id, col_id, _ = col_unit1
            # col_id=0 ("*") かつ 集計関数なし の場合のみ SELECT *
            # COUNT(*) 等は agg_id != 0 なので除外
            effective_agg = inner_agg_id if inner_agg_id != 0 else agg_id
            if col_id == 0 and effective_agg == 0:
                return True
    return False
```

## 処理フロー

```
┌─────────────────┐
│ SpiderExample   │
└────────┬────────┘
         │
         ▼
    SELECT * ?  ──Yes──▶ REFUSE
         │
         No
         ▼
    violations?  ──No──▶ SQL(original)
         │
         Yes
         ▼
┌─────────────────┐
│ Rewrite (Step6) │
└────────┬────────┘
         │
    success?  ──Yes──▶ SQL(rewritten)
         │
         No
         ▼
      REFUSE
```

## テストケース

```python
def test_no_violation():
    example = SpiderExample(query="SELECT name FROM users", ...)
    gold = generate_gold_label(example, [], None)
    assert gold.type == "SQL"
    assert gold.sql == "SELECT name FROM users"

def test_rewrite_success():
    rewrite_result = RewriteResult(True, sql="SELECT user_id FROM users")
    gold = generate_gold_label(example, [violation], rewrite_result)
    assert gold.type == "SQL"
    assert gold.sql == "SELECT user_id FROM users"

def test_rewrite_failure():
    rewrite_result = RewriteResult(False, reason="Hidden in WHERE")
    gold = generate_gold_label(example, [violation], rewrite_result)
    assert gold.type == "REFUSE"

def test_select_star():
    # SELECT * は REFUSE
    example = SpiderExample(query="SELECT * FROM users", ...)
    gold = generate_gold_label(example, [], None)
    assert gold.type == "REFUSE"

def test_count_star_not_refuse():
    # COUNT(*) は SELECT * ではない → REFUSE にならない
    example = SpiderExample(query="SELECT COUNT(*) FROM users", ...)
    # sql["select"] = (False, [(3, (0, (0, 0, False), None))])
    # agg_id=3 (count), col_id=0 (*) → SELECT * ではない
    gold = generate_gold_label(example, [], None)
    assert gold.type == "SQL"
```

## 完了条件

- 全パターンが正しく分岐する
- SELECT * が REFUSE になる
- rewrite 結果が正しく反映される
