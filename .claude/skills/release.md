---
name: release
description: バージョンアップとリリース作業を実施する
---

# リリーススキル

配布パッケージ（PyInstaller + zip、GitHub Releases経由で配布）のバージョンアップ・
公開手順。詳細は `docs/OPERATIONS.md` 7.4節を参照（重複記述を避けるため要点のみ記載）。

## 手順

1. `backend/pyproject.toml` の `[project].version` を更新する（アプリバージョンの
   単一の情報源。`frontend/package.json` のversionは対象外）
2. デプロイチェックを実施する

   ```bash
   cd backend
   uv run ruff check .
   uv run pytest
   ```

3. 配布パッケージをビルドする（`backend/build.bat` をダブルクリックでも可）

   ```bash
   uv run python scripts/build_package.py
   ```

4. GitHub Releasesへ公開する（`build_package.py`とは独立した、公開したいタイミングで
   開発者が明示的に実行するコマンド）

   ```bash
   uv run python scripts/publish_release.py
   ```

5. ユーザーにコミット & プッシュの実施を案内する
