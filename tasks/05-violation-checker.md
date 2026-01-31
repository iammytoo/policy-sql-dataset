# Step 05: Violation 検出

## 目的

列参照リストと Policy マップを照合し、違反を検出する。

## 入力

- `list[ColumnRef]`（Step 04 の出力）
- `dict[str, PolicyType]`（Step 03 の出力）

## 出力

```python
list[Violation]
```

## タスク

- [ ] Policy × Role 許可表の実装
- [ ] 各列参照の違反チェック
- [ ] COUNT(*) の例外処理
- [ ] AggOnly の AVG/COUNT 限定チェック

## 実装: violation_checker.py

```python
# Policy × Role 許可表
PERMISSION_TABLE: dict[PolicyType, dict[RoleType, bool]] = {
    "Public": {
        "SelectExpr": True,
        "JoinCond": True,
        "WherePred": True,
        "AggArg": True,
    },
    "JoinOnly": {
        "SelectExpr": False,
        "JoinCond": True,
        "WherePred": True,
        "AggArg": False,
    },
    "AggOnly": {
        "SelectExpr": False,
        "JoinCond": False,
        "WherePred": False,
        "AggArg": True,  # ただし AVG/COUNT のみ
    },
    "Hidden": {
        "SelectExpr": False,
        "JoinCond": False,
        "WherePred": False,
        "AggArg": False,
    },
}

# AggOnly で許可される agg_id
AGGONLY_ALLOWED_AGGS = {3, 5}  # count=3, avg=5

def check_violations(
    refs: list[ColumnRef],
    policies: dict[str, PolicyType]
) -> list[Violation]:
    """列参照リストから違反を検出"""
    violations = []

    for ref in refs:
        col_key = f"{ref.table}.{ref.column}"
        policy = policies.get(col_key, "Public")

        if not is_allowed(policy, ref.role, ref.agg_id):
            violations.append(Violation(
                column=col_key,
                role=ref.role,
                policy=policy,
                agg_id=ref.agg_id
            ))

    return violations

def is_allowed(policy: PolicyType, role: RoleType, agg_id: int) -> bool:
    """許可判定"""
    # 基本の許可表をチェック
    if not PERMISSION_TABLE[policy][role]:
        return False

    # AggOnly の追加チェック: AVG/COUNT のみ許可
    if policy == "AggOnly" and role == "AggArg":
        if agg_id not in AGGONLY_ALLOWED_AGGS:
            return False

    return True
```

## 例

```python
# JoinOnly 列を SELECT している場合
ref = ColumnRef("users", "user_id", "SelectExpr", 0)
policies = {"users.user_id": "JoinOnly"}

violations = check_violations([ref], policies)
# → [Violation("users.user_id", "SelectExpr", "JoinOnly", 0)]

# AggOnly 列を AVG で使っている場合（許可）
ref = ColumnRef("employees", "salary", "AggArg", 5)
policies = {"employees.salary": "AggOnly"}

violations = check_violations([ref], policies)
# → []（違反なし）

# AggOnly 列を SUM で使っている場合（違反）
ref = ColumnRef("employees", "salary", "AggArg", 4)  # sum=4
violations = check_violations([ref], policies)
# → [Violation("employees.salary", "AggArg", "AggOnly", 4)]
```

## テストケース

```python
def test_public_all_allowed():
    refs = [ColumnRef("t", "c", role, 0) for role in ["SelectExpr", "JoinCond", "WherePred"]]
    violations = check_violations(refs, {"t.c": "Public"})
    assert len(violations) == 0

def test_hidden_all_denied():
    refs = [ColumnRef("t", "c", role, 0) for role in ["SelectExpr", "JoinCond", "WherePred"]]
    violations = check_violations(refs, {"t.c": "Hidden"})
    assert len(violations) == 3

def test_aggonly_avg_allowed():
    ref = ColumnRef("t", "c", "AggArg", 5)
    violations = check_violations([ref], {"t.c": "AggOnly"})
    assert len(violations) == 0

def test_aggonly_sum_denied():
    ref = ColumnRef("t", "c", "AggArg", 4)
    violations = check_violations([ref], {"t.c": "AggOnly"})
    assert len(violations) == 1
```

## 完了条件

- 許可表が仕様通り動作する
- AggOnly の AVG/COUNT 限定が機能する
- 全テストケースが通る
