# Step 01: プロジェクトセットアップ

## 目的

Python プロジェクトの基盤を構築する。

## タスク

- [ ] `pyproject.toml` 作成（依存関係定義）
- [ ] `src/` ディレクトリ構造作成
- [ ] `data/` 出力ディレクトリ作成
- [ ] 基本的な型定義（dataclass / TypedDict）

## ディレクトリ構造

```
src/
├── __init__.py
├── main.py              # エントリポイント
├── types.py             # 型定義
├── spider_loader.py     # Step 02
├── policy_assigner.py   # Step 03
├── role_extractor.py    # Step 04
├── violation_checker.py # Step 05
├── rewriter.py          # Step 06
├── gold_generator.py    # Step 07
├── negative_generator.py # Step 08
├── output_writer.py     # Step 09
└── qa_checker.py        # Step 10
```

## 依存パッケージ

```toml
[project]
dependencies = [
    "tqdm",      # 進捗表示
]

[project.optional-dependencies]
dev = [
    "pytest",
    "ruff",
]
```

## 型定義（types.py）

```python
from dataclasses import dataclass
from typing import Literal

PolicyType = Literal["Public", "JoinOnly", "AggOnly", "Hidden"]
RoleType = Literal["SelectExpr", "JoinCond", "WherePred", "AggArg"]
GoldLabelType = Literal["SQL", "REFUSE"]

@dataclass
class ColumnRef:
    table: str
    column: str
    role: RoleType
    agg_id: int

@dataclass
class Violation:
    column: str  # "table.column"
    role: RoleType
    policy: PolicyType
    agg_id: int

@dataclass
class GoldLabel:
    type: GoldLabelType
    sql: str | None

@dataclass
class NegativeExample:
    sql: str
    violations: list[Violation]
```

## 完了条件

- `python -c "from src import types"` が成功する
- ruff check が通る
