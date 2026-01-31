# Policy SQL Dataset

Text2SQL において列ごとの usage policy を遵守できるかを評価するデータセット構築プロジェクト。

## 概要

- **ベース**: Spider 1.0
- **目的**: 「構文的に正しいが policy 違反な SQL」を検出・評価可能にする
- **Policy 型**: Public / JoinOnly / AggOnly / Hidden
- **Role**: SelectExpr / JoinCond / WherePred / AggArg

## ディレクトリ構造

```
policy-sql-dataset/
├── docs/
│   └── spec.md           # 正式仕様書
├── tasks/                # 実装計画
├── src/                  # 実装コード
├── data/                 # 生成データ出力先
├── spider_data/          # Spider データセット（入力）
└── spider-master/        # Spider 公式コード
```

## 重要な設計決定

1. **パーサ不要**: Spider の `sql` フィールド（パース済みAST）をそのまま使用
2. **Policy 優先順位**: `*_id` → Hidden(email/phone/address) → AggOnly → Public
3. **SELECT ***: REFUSE 扱い（展開しない）
4. **Rewrite**: 意味保存を保証しない（policy 準拠の近似）
5. **Negative**: 1問につき1件、編集距離1

## Spider AST 構造

```python
# 列参照
col_unit = (agg_id, col_id, isDistinct)
# agg_id: 0=none, 1=max, 2=min, 3=count, 4=sum, 5=avg
# col_id: 0="*", 1以降は tables.json のインデックス

# SQL構造
sql['select']        # SELECT 句
sql['from']['conds'] # JOIN 条件
sql['where']         # WHERE 句
```

## 開発時の注意

- 仕様の詳細は `docs/spec.md` を参照
- Spider データは `spider_data/spider_data/` にある（二重ネスト注意）
- `tables.json` で col_id → table.column の解決が必要
