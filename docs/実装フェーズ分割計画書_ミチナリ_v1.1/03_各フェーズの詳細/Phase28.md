### Phase 28：リソース配分データモデル拡張

| 項目 | 内容 |
| --- | --- |
| 目的 | スロット単位の配分と、実績の時間枠別内訳を保持できるようにデータモデルを拡張する |
| 投入文書 | CLAUDE.md、運用設計ルール、設計書 データ構造編（1.1改19）、実装フェーズ分割計画書（本フェーズ） |

**実装対象**

- `goal_slot_allocation`・`study_log_slot_time`・`reading_log_slot_time` の3モデルを新設
- `goal.resource_ratio` を削除、`reading_log.minutes_spent` を追加
- Alembicリビジョンを追加（SQLiteのため `batch_alter_table` を用いる）。データ移行として、既存の `resource_ratio` を「比率 × 各スロットの連続時間（分）」で各スロットへ按分し `goal_slot_allocation` へ転記する。端数は切り捨て、按分後の合計がスロット容量を超えないことを保証する。移行時点でスロットが1件も無い場合は転記対象が無いため、配分は空のまま引き継ぐ（`resource_ratio` が正の値だった目標は再設定が必要になるため、移行ログに出力する）
- 既存の `study_log.minutes_spent` はそのまま残し、内訳（`study_log_slot_time`）を持たない状態で引き継ぐ

**Phase 28完了（2026-09-10）。**

**完了条件**

- `alembic upgrade head` でスキーマが構築される
- 既存DBからのアップグレードで、配分と学習実績が失われないこと（`tests/migration_helpers.py` の `upgrade_to` により、対象リビジョンの前後で検証する）
- バックエンドの既存テストが、`resource_ratio` を参照する箇所の書き換えを除いて成功する

---

