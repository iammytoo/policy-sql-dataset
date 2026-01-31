# Step 02: Spider データ読み込み

## 目的

Spider データセットを読み込み、内部データ構造に変換する。

## 入力ファイル

```
spider_data/spider_data/
├── tables.json        # スキーマ定義
├── train_spider.json  # 訓練データ
├── dev.json           # 開発データ
└── test.json          # テストデータ
```

## タスク

- [ ] `tables.json` を読み込み、DB別スキーマを構築
- [ ] col_id → "table.column" の解決マップを作成
- [ ] train/dev/test の各 JSON を読み込み
- [ ] 各レコードを内部型に変換

## 実装: spider_loader.py

```python
@dataclass
class TableSchema:
    db_id: str
    tables: list[str]                    # テーブル名リスト
    columns: dict[int, str]              # col_id → "table.column"
    primary_keys: set[int]               # PK の col_id
    column_names: dict[str, list[str]]   # table → [columns]

@dataclass
class SpiderExample:
    db_id: str
    question: str
    query: str          # 元のSQL文字列
    sql: dict           # パース済みAST

def load_schemas(tables_path: str) -> dict[str, TableSchema]:
    """tables.json を読み込み、db_id → TableSchema のマップを返す"""
    pass

def load_examples(json_path: str) -> list[SpiderExample]:
    """train/dev/test.json を読み込む"""
    pass

def resolve_column(schema: TableSchema, col_id: int) -> str:
    """col_id を "table.column" 形式に解決"""
    pass
```

## col_id 解決ロジック

```python
# tables.json の構造
{
  "column_names_original": [
    [-1, "*"],      # col_id=0
    [0, "id"],      # col_id=1, table_idx=0
    [0, "name"],    # col_id=2, table_idx=0
    [1, "user_id"], # col_id=3, table_idx=1
  ],
  "table_names_original": ["users", "orders"]
}

# col_id=0 → "*"
# col_id=1 → "users.id"
# col_id=3 → "orders.user_id"
```

## テストケース

```python
def test_resolve_column():
    schema = load_schemas("spider_data/spider_data/tables.json")["concert_singer"]
    assert resolve_column(schema, 0) == "*"
    assert resolve_column(schema, 1) == "stadium.stadium_id"
```

## 完了条件

- 全 166 DB のスキーマが正しく読み込める
- train/dev/test の全レコードが読み込める
- col_id 解決が正しく動作する
