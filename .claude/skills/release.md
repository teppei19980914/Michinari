---
name: release
description: バージョンアップとリリース作業を実施する
---

# リリーススキル

配布パッケージ（PyInstaller + zip、GitHub Releases経由で配布）のバージョンアップ・
公開手順。詳細は `docs/OPERATIONS.md` 7.4節を参照（重複記述を避けるため要点のみ記載）。

## 手順

**順序が重要**。ビルドより先にバージョン更新とリリースノートをコミットし、`main` へ
マージしてからビルドする。この順序を崩すと、タグが配布物と異なるコミットを指す
（OPERATIONS.md 7.4「タグは必ずビルド元コミットへ付ける」参照）。

1. `backend/pyproject.toml` の `[project].version` を更新する（アプリバージョンの
   単一の情報源。`frontend/package.json` のversionは対象外）
2. `docs/release-notes/v{version}.md` を作成する（未作成だと手順7がエラー終了する）。
   全変更点を書き、冒頭に `<!-- summary:start -->` 〜 `<!-- summary:end -->` で囲んだ
   要約（15行以内。破壊的変更・移行時の注意を必ず含める）を置く。
   `docs/release-notes/README.md` の表にも1行追加する。書き方は同ファイルを参照
3. デプロイチェックを実施する

   ```bash
   cd backend
   uv run ruff check .
   uv run pytest
   ```

4. 1〜2をコミットし、`main` へマージする。**ビルドは作業ツリーがクリーンな状態で行う**
   （未コミットの木からのビルドは対応するコミットが無いため、手順7が公開を中止する）
5. 配布パッケージをビルドする（`backend/build.bat` をダブルクリックでも可）。
   **バージョン入力では手順1で確定した値と同じ値を入力する**（別の値を入れると
   `pyproject.toml` が書き換わり、作業ツリーが汚れる）

   ```bash
   uv run python scripts/build_package.py
   ```

6. `git fetch origin main` でリモート参照を最新化する（手順7のマージ済み判定が
   ローカルの `origin/main` を見るため）
7. GitHub Releasesへ公開する（`build_package.py`とは独立した、公開したいタイミングで
   開発者が明示的に実行するコマンド）

   ```bash
   uv run python scripts/publish_release.py
   ```

8. ユーザーにコミット & プッシュの実施を案内する
