# 実装計画 Overview

## ゴール

Spider データセットに Policy を付与し、violation 検出・rewrite・gold label 生成を行い、評価用データセットを出力する。

## ステップ一覧

| Step | タスク | 入力 | 出力 |
|------|--------|------|------|
| 01 | プロジェクトセットアップ | - | src/, data/, pyproject.toml |
| 02 | Spider データ読み込み | spider_data/ | 内部データ構造 |
| 03 | Policy 自動付与 | tables.json | policies/{db_id}.json |
| 04 | Role 抽出 | sql AST | 列参照リスト (col, role, agg_id) |
| 05 | Violation 検出 | 列参照 + policies | violations リスト |
| 06 | Rewrite 処理 | violations + sql | rewritten_sql or REFUSE |
| 07 | Gold Label 生成 | original + rewrite結果 | gold_label |
| 08 | Negative Example 生成 | original_sql + policies | negative_examples |
| 09 | 出力生成 | 全処理結果 | train.json, dev.json, test.json |
| 10 | QA チェック | 出力データ | 統計レポート |

## 依存関係

```
01 → 02 → 03 ─┬→ 04 → 05 → 06 → 07 ─┬→ 09 → 10
              └→ 08 ─────────────────┘
```

> **注**: Step 08（Negative 生成）は Step 03（Policy 付与）の直後から並行して実行可能。Step 05（Violation 検出）には依存しない。

## 実行方法（完成後）

```bash
python -m src.main --input spider_data/spider_data --output data/
```
