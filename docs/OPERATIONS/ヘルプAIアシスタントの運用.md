## ヘルプAIアシスタントの運用（1.1改43、Phase43）

### ヘルプ本文の書き出し（開発時、ヘルプ文言を変えたとき）

ヘルプAIアシスタントが根拠にするヘルプ本文は、`frontend/src/locales/ja.json` の `help` から書き出す。`ja.json` を変えたら、次を `backend` で実行し、生成物（`backend/app/content/help_content.json`）も版管理に含める。

    uv run python scripts/export_help_content.py

生成物が `ja.json` と食い違っていると、テスト（`tests/test_help_content.py`）が失敗する。リリース前の確認で必ず通すこと。配布物には `build_package` が `app/content/help_content.json` を同梱する。

### 禁止語の管理

禁止語は `ai_forbidden_term` テーブルで管理する（画面からの編集は未実装）。質問に禁止語を含むと、AIへは送らず「この質問には回答できません」と表示される。

- 追加・無効化は、SQLiteの操作ツールで行う（`enabled = 0` で無効化。誤検出の対処に使う）。
- 初期一覧は `backend/app/init/seed_data.py` の `INITIAL_FORBIDDEN_TERMS`（起動時に不足分のみ投入）。
- 禁止語の照合は正規化後に行うため、全角・空白の挿入では回避できない。

### 質問用のチャットとフォルダ

- 質問ごとに新しいチャットを作り、回答後に削除する。削除は一覧で確認し、残っていれば `logs` に警告が出る。
- チャットは `ai.help_folder_name`（既定 `ミチナリ_ヘルプ`）のフォルダへ作る。フォルダは開発キット（NewtonX）側に残るため、不要になった場合は NewtonX の画面から手動で削除する（開発キットには削除APIが無い）。
- 質問・回答は既存の `ai_log`（用途 `HELP_ASSISTANT`）に記録される。保持期間は `log.retention_days` に従う。

### 利用上の注意

- 回答には免責文（「AIの回答は誤る場合があります」）が常に表示される。
- 質問の上限は300字（`ai.help_question_max_chars`）。回答の上限は2000字（`ai.help_answer_max_chars`）。
- 使用アシスタントは `ai.assistant_uid.help`（既定：GPT-5 mini（高速）、ナレッジなし）。変更は設定画面の「ヘルプ質問用アシスタント」から行う。
