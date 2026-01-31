# Step 06: Rewrite 処理

## 目的

違反を解消するための SQL 書き換えを試みる。

## 入力

- `query`（元の SQL 文字列）
- `sql`（AST）
- `violations`（Step 05 の出力）
- `schema`（PK 情報用）
- `policies`

## 出力

```python
RewriteResult:
  success: bool
  sql: str | None      # 成功時のみ
  reason: str | None   # 失敗時の理由
```

## タスク

- [ ] R1: SelectExpr の Hidden/JoinOnly → `*_id` 置換
- [ ] R2: SelectExpr の AggOnly → `AVG(col)` 置換
- [ ] R3: WherePred/JoinCond の Hidden → REFUSE
- [ ] R4: AggArg の AggOnly 列が AVG/COUNT 以外 → REFUSE
- [ ] 最大 2 ステップの適用
- [ ] SQL 文字列の再構築

## 実装: rewriter.py

```python
@dataclass
class RewriteResult:
    success: bool
    sql: str | None = None
    reason: str | None = None

def rewrite(
    query: str,
    sql: dict,
    violations: list[Violation],
    schema: TableSchema,
    policies: dict[str, PolicyType]
) -> RewriteResult:
    """違反を解消する書き換えを試みる"""

    # R3: WHERE/JOIN に Hidden または AggOnly があれば即 REFUSE
    # (JoinOnly は WherePred/JoinCond で許可されるのでここでは対象外)
    for v in violations:
        if v.role in ("WherePred", "JoinCond") and v.policy in ("Hidden", "AggOnly"):
            return RewriteResult(False, reason=f"{v.policy} column in {v.role}: {v.column}")

    # R4: AggArg に AggOnly 列が AVG/COUNT 以外で使われていれば即 REFUSE
    # (AggOnly は agg_id=3(count) または agg_id=5(avg) のみ許可)
    for v in violations:
        if v.role == "AggArg" and v.policy == "AggOnly" and v.agg_id not in (3, 5):
            return RewriteResult(False, reason=f"AggOnly column with non-AVG/COUNT agg: {v.column}")

    # SELECT 句の違反のみを処理
    select_violations = [v for v in violations if v.role == "SelectExpr"]
    if not select_violations:
        # AggArg の違反のみ → 書き換え不可
        agg_violations = [v for v in violations if v.role == "AggArg"]
        if agg_violations:
            return RewriteResult(False, reason="AggArg violation cannot be rewritten")
        return RewriteResult(True, sql=query)

    # 書き換え適用（最大2ステップ）
    current_query = query
    for step in range(2):
        current_query, remaining = _apply_rewrite_step(
            current_query, select_violations, schema, policies
        )
        if not remaining:
            return RewriteResult(True, sql=current_query)
        select_violations = remaining

    return RewriteResult(False, reason="Rewrite limit exceeded")

def _apply_rewrite_step(
    query: str,
    violations: list[Violation],
    schema: TableSchema,
    policies: dict[str, PolicyType]
) -> tuple[str, list[Violation]]:
    """1ステップの書き換えを適用"""
    remaining = []

    for v in violations:
        if v.policy in ("Hidden", "JoinOnly"):
            # R1: *_id 列で置換
            replacement = _find_id_column(v.column, schema, policies)
            if replacement:
                query = _replace_column(query, v.column, replacement)
            else:
                remaining.append(v)

        elif v.policy == "AggOnly":
            # R2: AVG(col) で置換
            # 注: policy は列ごとに1つなので AggOnly 列は Hidden ではありえない
            col_name = v.column.split(".")[-1]
            query = _wrap_with_avg(query, col_name)

    return query, remaining

def _find_id_column(
    column: str,
    schema: TableSchema,
    policies: dict[str, PolicyType]
) -> str | None:
    """同テーブル内の *_id 列を探す（PK優先）"""
    table = column.split(".")[0]
    candidates = []

    for col_id, full_name in schema.columns.items():
        if not full_name.startswith(f"{table}."):
            continue
        if policies.get(full_name) == "JoinOnly":
            # PK かどうかをチェック
            is_pk = col_id in schema.primary_keys
            candidates.append((is_pk, full_name))

    if not candidates:
        return None

    # PK を優先してソート
    candidates.sort(key=lambda x: (not x[0], x[1]))
    return candidates[0][1]

def _replace_column(query: str, old_col: str, new_col: str) -> str:
    """SQL 文字列中の列名を置換"""
    # 簡易実装: 列名部分のみ置換
    old_name = old_col.split(".")[-1]
    new_name = new_col.split(".")[-1]
    # TODO: より堅牢な置換（エイリアス考慮）
    return query.replace(old_name, new_name)

def _wrap_with_avg(query: str, col_name: str) -> str:
    """列を AVG() で包む"""
    # SELECT col → SELECT AVG(col)
    import re
    pattern = rf'\bSELECT\s+{col_name}\b'
    replacement = f'SELECT AVG({col_name})'
    return re.sub(pattern, replacement, query, flags=re.IGNORECASE)
```

## 注意点

### SQL 文字列の再構築

v1 では簡易的な文字列置換を行う。完全な AST → SQL 再構築は行わない。

### 置換の限界

- エイリアスがある場合の処理は不完全
- 複雑なネストには対応しない
- 失敗した場合は REFUSE にフォールバック

## テストケース

```python
def test_rewrite_joinonly_to_id():
    query = "SELECT name FROM users"
    violations = [Violation("users.name", "SelectExpr", "JoinOnly", 0)]
    result = rewrite(query, sql, violations, schema, policies)
    assert result.success
    assert "user_id" in result.sql

def test_rewrite_hidden_in_where_refuse():
    violations = [Violation("users.email", "WherePred", "Hidden", 0)]
    result = rewrite(query, sql, violations, schema, policies)
    assert not result.success
    assert "Hidden" in result.reason

def test_rewrite_aggonly_in_where_refuse():
    # WHERE salary > 50000 のようなケース
    # AggOnly 列は WHERE では使用不可（集計関数で包んでも不可）
    violations = [Violation("employees.salary", "WherePred", "AggOnly", 0)]
    result = rewrite(query, sql, violations, schema, policies)
    assert not result.success
    assert "AggOnly" in result.reason

def test_rewrite_aggonly_in_join_refuse():
    # JOIN ON t1.salary = t2.salary のようなケース
    violations = [Violation("employees.salary", "JoinCond", "AggOnly", 0)]
    result = rewrite(query, sql, violations, schema, policies)
    assert not result.success
    assert "AggOnly" in result.reason
```

## 完了条件

- R1/R2/R3/R4 が仕様通り動作する
- PK 優先の置換が機能する
- 失敗時は適切な理由が返される
