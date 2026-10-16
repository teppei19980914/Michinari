### Phase 1：基盤構築

| 項目 | 内容 |
| --- | --- |
| 目的 | プロジェクト構成とデータ永続化層を確立する |
| 投入文書 | CLAUDE.md、運用設計ルール、設計書 データ構造編（全体） |

**実装対象**

1. ディレクトリ構成の作成（設計書 データ構造編 第8章）
2. Python環境とパッケージ管理の設定
3. FastAPI の起動設定（**ポート8400を避ける。既定値8100**）
4. SQLAlchemy のセッション管理、`PRAGMA foreign_keys = ON` の設定
5. 全 Enum の定義（backend/app/constants/）
6. 全 SQLAlchemy モデルの定義（`ai_conversation`、`goal_retrospective` を含む）
7. Alembic の初期化と初回リビジョン生成
8. 初期データ投入処理（app_setting、prompt_template、day_type_default）
9. `/health` エンドポイント

**完了条件**

- `alembic upgrade head` でデータベースが構築される
- 起動時に初期データが投入され、再起動しても重複しない
- `/health` が応答する
- 全テーブルに対する基本的なCRUDが動作することを確認できる
- `material` に `planned_cycles` が存在し、`current_cycle` が存在しない

**注意点**

- **マイグレーションSQLを目視レビューすること。** Alembicの自動生成は複合主キーや制約の扱いを誤ることがある
- 初期データ投入はマイグレーションではなくアプリケーション起動時に行う。データとスキーマを分離するため
- プロンプトテンプレートの初期文面は設計書 ロジック・プロンプト編 第17章から転記する。要約や改変をしないこと

---

