# Step 04: Role 抽出

## 目的

Spider AST を走査し、全ての列参照を (col_id, role, agg_id) として抽出する。

## 入力

- `sql`（Spider パース済み AST）
- `TableSchema`（col_id 解決用）

## 出力

```python
list[ColumnRef]  # [(table, column, role, agg_id), ...]
```

## タスク

- [ ] SELECT 句の走査 → SelectExpr / AggArg
- [ ] FROM 句の JOIN 条件走査 → JoinCond
- [ ] WHERE 句の走査 → WherePred
- [ ] サブクエリの再帰処理
- [ ] INTERSECT/UNION/EXCEPT の処理

## 実装: role_extractor.py

```python
def extract_roles(sql: dict, schema: TableSchema) -> list[ColumnRef]:
    """AST から全列参照を抽出"""
    refs = []
    refs.extend(_extract_from_select(sql["select"], schema))
    refs.extend(_extract_from_conds(sql["from"]["conds"], schema, "JoinCond"))
    refs.extend(_extract_from_conds(sql["where"], schema, "WherePred"))

    # サブクエリ処理
    for table_unit in sql["from"]["table_units"]:
        if table_unit[0] == "sql":
            refs.extend(extract_roles(table_unit[1], schema))

    # INTERSECT/UNION/EXCEPT
    for op in ["intersect", "union", "except"]:
        if sql.get(op):
            refs.extend(extract_roles(sql[op], schema))

    return refs

def _extract_from_select(select: tuple, schema: TableSchema) -> list[ColumnRef]:
    """SELECT 句から列参照を抽出"""
    is_distinct, val_units = select
    refs = []
    for agg_id, val_unit in val_units:
        refs.extend(_extract_from_val_unit(val_unit, schema, agg_id))
    return refs

def _extract_from_val_unit(
    val_unit: tuple,
    schema: TableSchema,
    outer_agg_id: int
) -> list[ColumnRef]:
    """val_unit から列参照を抽出"""
    unit_op, col_unit1, col_unit2 = val_unit
    refs = []

    for col_unit in [col_unit1, col_unit2]:
        if col_unit is None:
            continue
        agg_id, col_id, is_distinct = col_unit

        # 実効 agg_id: col_unit 自身か outer のどちらか非ゼロを採用
        effective_agg = agg_id if agg_id != 0 else outer_agg_id

        # Role 決定
        if effective_agg != 0:
            role = "AggArg"
        else:
            role = "SelectExpr"

        col_name = resolve_column(schema, col_id)
        if col_name != "*":
            table, column = col_name.split(".", 1)
            refs.append(ColumnRef(table, column, role, effective_agg))

    return refs

def _extract_from_conds(
    conds: list,
    schema: TableSchema,
    role: RoleType  # "JoinCond" or "WherePred"
) -> list[ColumnRef]:
    """条件式から列参照を抽出"""
    refs = []
    for item in conds:
        if isinstance(item, str):  # "and" / "or"
            continue
        not_op, op_id, val_unit, val1, val2 = item
        # 条件式内の列には渡された role を付与
        refs.extend(_extract_cols_from_val_unit(val_unit, schema, role))
        # val1, val2 がサブクエリの場合は再帰
        for val in [val1, val2]:
            if isinstance(val, dict):  # サブクエリ
                refs.extend(extract_roles(val, schema))
            # val1, val2 が col_unit の場合もある
            elif isinstance(val, (list, tuple)) and len(val) == 3:
                col_id = val[1]
                if col_id != 0:  # "*" でなければ
                    col_name = resolve_column(schema, col_id)
                    if col_name != "*":
                        table, column = col_name.split(".", 1)
                        refs.append(ColumnRef(table, column, role, 0))
    return refs

def _extract_cols_from_val_unit(
    val_unit: tuple,
    schema: TableSchema,
    role: RoleType
) -> list[ColumnRef]:
    """val_unit から列参照を抽出（条件式用、roleを直接指定）"""
    unit_op, col_unit1, col_unit2 = val_unit
    refs = []

    for col_unit in [col_unit1, col_unit2]:
        if col_unit is None:
            continue
        agg_id, col_id, is_distinct = col_unit

        col_name = resolve_column(schema, col_id)
        if col_name != "*":
            table, column = col_name.split(".", 1)
            refs.append(ColumnRef(table, column, role, agg_id))

    return refs
```

## 注意点

### AggArg の判定

```python
# SELECT AVG(salary) の場合
# val_unit 内: agg_id=5 (avg), col_id=salary のインデックス
# → role = AggArg

# SELECT COUNT(*) の場合
# col_id=0 ("*") → 列参照としては記録しない（常に許可）
```

### GROUP BY / HAVING / ORDER BY

仕様により**無視する**（走査しない）。

## テストケース

```python
def test_simple_select():
    sql = {"select": (False, [(0, (0, (0, 1, False), None))]), ...}
    refs = extract_roles(sql, schema)
    assert refs[0].role == "SelectExpr"

def test_agg_select():
    # SELECT AVG(salary)
    sql = {"select": (False, [(5, (0, (0, 3, False), None))]), ...}
    refs = extract_roles(sql, schema)
    assert refs[0].role == "AggArg"
    assert refs[0].agg_id == 5

def test_where_role():
    # SELECT name FROM users WHERE user_id = 1
    # user_id は WherePred になるべき
    sql = {
        "select": ...,
        "from": {"table_units": [...], "conds": []},
        "where": [(False, 2, (0, (0, 3, False), None), 1, None)]  # user_id = 1
    }
    refs = extract_roles(sql, schema)
    where_refs = [r for r in refs if r.role == "WherePred"]
    assert len(where_refs) >= 1
    assert where_refs[0].column == "user_id"

def test_join_role():
    # JOIN ON a.id = b.a_id
    # 両方の列が JoinCond になるべき
    sql = {
        "select": ...,
        "from": {
            "table_units": [...],
            "conds": [(False, 2, (0, (0, 1, False), None), (0, 2, False), None)]
        },
        "where": []
    }
    refs = extract_roles(sql, schema)
    join_refs = [r for r in refs if r.role == "JoinCond"]
    assert len(join_refs) == 2
```

## 完了条件

- 全ての role が正しく抽出される
- サブクエリ内の列も抽出される
- COUNT(*) は列参照として記録されない
