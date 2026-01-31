# Spider データ分析メモ

分析日: 2025-01-31
対象: spider_data/spider_data/

## 1. 基本統計

| 項目 | 値 |
|------|-----|
| 総DB数 | 166 |
| 総列数 | 4,503 |
| dev.json レコード数 | 1,034 |

## 2. 列名パターン分布

Policy 自動付与ルールの根拠となる数値。

### 分析コード

```python
import json
import re

with open('spider_data/spider_data/tables.json') as f:
    tables = json.load(f)

all_columns = []
for db in tables:
    for col in db['column_names_original']:
        if col[0] != -1:
            all_columns.append(col[1].lower())
```

### 結果

| パターン | 件数 | 割合 | Policy |
|----------|------|------|--------|
| `*_id` / `id_*` / `^id$` | 1,074 | 23.9% | JoinOnly |
| `email` を含む | 31 | 0.7% | Hidden |
| `phone` を含む | 39 | 0.9% | Hidden |
| `address` を含む | 109 | 2.4% | Hidden（ただし競合あり） |
| `salary/income/price/amount` | 70 | 1.6% | AggOnly |
| その他 | 3,180 | 70.6% | Public |

### サンプル

```
email: ['customer_email', 'store_email', 'email_address', 'email', ...]
phone: ['supplier_phone', 'customer_phone', 'home_phone', 'phone', ...]
salary等: ['salary', 'product_price', 'total_amount_purchased', 'price', ...]
```

## 3. パターン競合の分析

`address` と `*_id` の両方にマッチする列が存在する。

```python
address_cols = [c for c in all_columns if 'address' in c]
address_id_cols = [c for c in address_cols if re.search(r'_id$|^id_|^id$', c)]
```

### 結果

| 競合パターン | 件数 | 例 |
|--------------|------|-----|
| `address` かつ `*_id` | 40 | address_id, customer_address_id, staff_address_id |
| `phone` かつ `*_id` | 2 | phone_id |

### 決定

**`*_id` を先に判定** → これらは JoinOnly になる（住所IDは個人情報ではない）

## 4. SQL パターン分布

dev.json を対象に分析。

### 分析コード

```python
with open('spider_data/spider_data/dev.json') as f:
    dev = json.load(f)
```

### 結果

| パターン | 件数 | 割合 | 仕様への影響 |
|----------|------|------|--------------|
| JOIN あり | 408 | 39.5% | JoinCond role が重要 |
| サブクエリあり | 159 | 15.4% | 再帰処理が必須 |
| GROUP BY あり | 277 | 26.8% | 仕様により無視 |
| INTERSECT/UNION/EXCEPT | 80 | 7.7% | 再帰処理が必要 |
| SELECT * | 3 | 0.3% | REFUSE で問題なし |

### 決定根拠

- **SELECT ***: 0.3% のみなので REFUSE 扱いでも影響軽微
- **サブクエリ**: 15.4% あるので対応必須（無視できない）
- **GROUP BY**: 26.8% あるが仕様で無視と決定済み

## 5. JOINクエリのサンプル

```sql
SELECT T2.name, count(*)
FROM concert AS T1
JOIN stadium AS T2 ON T1.stadium_id = T2.stadium_id
GROUP BY T1.stadium_id

SELECT T2.name, T2.capacity
FROM concert AS T1
JOIN stadium AS T2 ON T1.stadium_id = T2.stadium_id
WHERE T1.year >= 2014
GROUP BY T2.stadium_id
ORDER BY count(*) DESC
LIMIT 1
```

## 6. tables.json 構造

```json
{
  "db_id": "perpetrator",
  "table_names_original": ["perpetrator", "people"],
  "column_names_original": [
    [-1, "*"],           // col_id=0
    [0, "Perpetrator_ID"], // col_id=1, table_idx=0
    [0, "People_ID"],      // col_id=2, table_idx=0
    [1, "People_ID"],      // col_id=3, table_idx=1
    [1, "Name"],           // col_id=4, table_idx=1
    ...
  ],
  "column_types": ["text", "number", ...],
  "primary_keys": [1, 3],
  "foreign_keys": [[2, 3]]
}
```

## 7. dev.json 構造（パース済みAST）

```json
{
  "db_id": "concert_singer",
  "question": "How many singers do we have?",
  "query": "SELECT count(*) FROM singer",
  "sql": {
    "select": [false, [[3, [0, [0, 0, false], null]]]],
    "from": {"table_units": [["table_unit", 1]], "conds": []},
    "where": [],
    "groupBy": [],
    "having": [],
    "orderBy": [],
    "limit": null,
    "intersect": null,
    "union": null,
    "except": null
  }
}
```

### sql.select の構造

```
(isDistinct, [(agg_id, val_unit), ...])

val_unit = (unit_op, col_unit1, col_unit2)
col_unit = (agg_id, col_id, isDistinct)

agg_id: 0=none, 1=max, 2=min, 3=count, 4=sum, 5=avg
col_id: 0="*", 1以降は column_names_original のインデックス
```

---

## 8. Policy ルール拡張分析（2026-01-31追加）

現状のルールでは AggOnly + Hidden が少なすぎる問題を分析。

### 現状ルール

```python
POLICY_RULES = [
    (1, re.compile(r'(^id$|_id$|^id_)', re.I), "JoinOnly"),
    (2, re.compile(r'(email|phone|address)', re.I), "Hidden"),
    (3, re.compile(r'(salary|income|price|amount)', re.I), "AggOnly"),
]
```

### 現状の分布

```
Public    : 3246 (72.1%)  ← 多すぎ
JoinOnly  : 1065 (23.7%)
AggOnly   :   70 ( 1.6%)  ← 少なすぎ
Hidden    :  122 ( 2.7%)  ← 少なすぎ
```

### 追加候補パターン分析

#### Hidden 候補

| パターン | 件数 | 例 |
|----------|------|-----|
| gender | 21 | gender, staff_gender, gender_code |
| sex | 14 | sex |
| birth | 29 | birthday, birthdate, birth_date, birth_year |
| nationality | 16 | nationality |
| ssn | 10 | ssn, super_ssn, mgr_ssn |
| password | 7 | password, customer_password |
| weight | 10 | weight, max_gross_weight |
| height | 14 | height, height_feet |

**注意**: `age` は誤マッチ多数（language, image, percentage 等に含まれる）→ `^age$` に限定

#### AggOnly 候補

| パターン | 件数 | 例 |
|----------|------|-----|
| cost | 6 | cost, replacement_cost, daily_hire_cost |
| budget | 12 | budget, budget_million, budget_in_billions |
| score | 8 | score, credit_score |
| rating | 19 | rating, overall_rating |
| balance | 3 | balance |
| total | 21 | total, total_amount, total_points |
| profit | 3 | profits_billion |
| revenue | 1 | revenue |

#### JoinOnly 候補

| パターン | 件数 | 例 |
|----------|------|-----|
| _code$ | 180 | role_code, document_type_code, city_code |
| stuid | 20 | stuid |

### 新ルール

```python
POLICY_RULES = [
    # 優先度1: ID系 → JoinOnly
    (1, re.compile(r'(^id$|_id$|^id_)', re.I), "JoinOnly"),
    (1, re.compile(r'_code$', re.I), "JoinOnly"),
    (1, re.compile(r'^stuid$', re.I), "JoinOnly"),

    # 優先度2: 個人情報 → Hidden
    (2, re.compile(r'(email|phone|address)', re.I), "Hidden"),
    (2, re.compile(r'(gender|^sex$|nationality)', re.I), "Hidden"),
    (2, re.compile(r'(birth|ssn|password)', re.I), "Hidden"),
    (2, re.compile(r'^(weight|height|age)$', re.I), "Hidden"),

    # 優先度3: 金額・スコア → AggOnly
    (3, re.compile(r'(salary|income|price|amount)', re.I), "AggOnly"),
    (3, re.compile(r'(cost|budget|balance|revenue|profit)', re.I), "AggOnly"),
    (3, re.compile(r'(score|rating|^total$)', re.I), "AggOnly"),
]
```

### 新ルールの分布

```
            Old     New
Public    : 72.1% → 63.2%  (-8.9%)
JoinOnly  : 23.7% → 28.1%  (+4.4%)
AggOnly   :  1.6% →  2.7%  (+1.1%)
Hidden    :  2.7% →  6.0%  (+3.3%)
```

**AggOnly + Hidden: 4.3% → 8.7%**（倍増）

### テーブル/DB 単位での分布

カラム割合が低くても、テーブル/DB カバレッジが重要。

#### テーブル単位

| 項目 | 数 | 割合 |
|------|------|------|
| 総テーブル数 | 876 | - |
| Hidden 列あり | 150 | 17.1% |
| AggOnly 列あり | 99 | 11.3% |
| JoinOnly 列あり | 700 | 79.9% |
| 何か制限あり | 742 | **84.7%** |

#### DB 単位

| 項目 | 数 | 割合 |
|------|------|------|
| 総 DB 数 | 166 | - |
| Hidden 列を含む | 97 | **58.4%** |
| AggOnly 列を含む | 67 | **40.4%** |
| Hidden or AggOnly あり | 127 | **76.5%** |

#### Hidden/AggOnly を含まない DB（39個）

```
flight_company, icfp_1, storm_record, race_track, academic,
decoration_competition, store_product, farm, flight_2, election, ...
```

これらの DB では JoinOnly 違反のみ発生する。

### 結論

- カラム割合は 8.7% でも、**84.7% のテーブル**に制限列がある
- **76.5% の DB** に Hidden か AggOnly が存在
- 新ルールで進める

---

## 参考: 分析実行ログ

```
$ python3 分析スクリプト

総DB数: 166
総列数: 4503

email: 31 件
phone: 39 件
address: 109 件
*_id / id_*: 1074 件
salary/income/price/amount: 70 件

address かつ *_id: 40
phone かつ *_id: 2

dev.json: 全1034件中 SELECT * を含むもの: 3件 (0.3%)
サブクエリあり: 159件 (15.4%)
JOINあり: 408件 (39.5%)
INTERSECT/UNION/EXCEPT: 80件 (7.7%)
GROUP BY: 277件 (26.8%)
```
