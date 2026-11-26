# 開発Todo：単語帳 出題導線改修（本書で全体を管理）

本書は、既存の単語帳機能（`開発Todo_単語帳_v1.0.md` 要件A〜F、mainマージ済み）に対する仕様修正の正（Single Common of Truth）である。対象は「単語帳（デッキ）をユーザーから隠し、1目標＝1単語帳に単純化する」「問題を解く導線を、デッキ詳細ページ経由から、全画面ヘッダー→目標クリックで直接『問題出題内容設定画面』に遷移する形に再構成する」の2点。既存の出題エンジン（`VocabQuizMode`・ローカル出題セッション・AIによる今日の復習向け生成）自体は変更しない。

作業は `dev/2026-11-26`（`origin/main` マージ直後）で行う。

## 0. 決定事項

### 0.1 利用者に確認し、回答を得て確定した事項

| # | 決定 |
| --- | --- |
| U1 | 単語帳（デッキ）はユーザーに見せない。1目標（EXAM）＝1単語帳に固定する。ユーザー操作は単語（カード）の追加/編集/削除のみ |
| U2 | 単語の種類はTERM（用語/意味）・SITUATION（状況/最善の対応）の2種を維持する |
| U3 | 出題形式の制約は現状維持：SITUATIONは常にFLASH_SITUATION固定（4択・入力式はTERM専用）。既存の `_effective_mode` のロジックは変更しない |
| U4 | 入力式（TYPED）は現状の非対称を維持：「単語を答える」方向のみ入力式を持ち、「意味を答える」方向には追加しない |
| U5 | 「意味/単語をランダムに答える」は新しい出題方向として追加する。粒度は**問題ごとにランダム**（セッション内で1問ずつ方向を抽選する） |
| U6 | 全画面ヘッダー「単語帳」タブ：目標一覧→目標クリックで、目標詳細を経由せず**「問題出題内容設定画面」に直接遷移**する（1目標1デッキのため、デッキ選択ステップは発生しない） |
| U7 | 目標詳細「単語帳」タブ：単語のCRUDのみを提供する。タブ上部に「今日の復習・AIフィードバックで使うか」トグル（既存`use_in_ai`）と「今日の復習の問題を作る」ボタン（既存のAI生成機能）を移設する |
| U8 | 単語帳名＋統計へのリンク（旧デッキ一覧からデッキ詳細への遷移）は廃止する |
| U9 | 既存の複数デッキを持つ目標（移行対象）は、`display_order`最小の1件にカードを統合（`deck_id`付け替え）し、他のデッキは削除する。カード・解答履歴（`vocab_answer_log`）は消さない |
| U10 | デッキのテーブル構造（`vocab_deck`）は維持する。目標作成時（EXAM）にバックエンドが自動で1行生成する |

### 0.2 実装上の判断（利用者確認は不要な技術的決定。根拠を併記）

| # | 決定 | 理由 |
| --- | --- | --- |
| D1 | `goal_service.create_goal`で`category == GoalCategory.EXAM`のとき、`session.flush()`後に`vocab_service.create_deck(session, goal, name=goal.name, description=None)`を呼び、デッキを自動作成する | 既存の`create_deck`はEXAM以外を拒否するガードを既に持つ（`vocab_service.py:125-126`）ため、呼び出し側でのカテゴリ分岐のみで足りる |
| D2 | 自動作成するデッキの`name`は目標名をそのまま複写する（以後、目標名が変更されてもデッキ名は追従させない） | デッキ名はユーザーに表示しない内部識別子になるが、インポート/エクスポートのファイル名生成（`VocabImportExportPanel`）に使われているため、空文字や固定文字列より目標名の方が識別しやすい。追従処理は本改修のスコープ外（表示しない値の同期コストをかけない、過剰設計を避ける） |
| D3 | 移行バッチは新規Alembicマイグレーション1本で実装し、(a) 複数デッキを持つEXAM目標はカードを`display_order`最小のデッキへ`UPDATE vocab_card SET deck_id=...`で付け替えてから余剰デッキを削除、(b) デッキが0件のEXAM目標には目標名でデッキを1件作成、の順に行う | データ移行はアプリ起動時ではなくマイグレーションで確定的に1回だけ行う（既存の全マイグレーションと同じ方式）。カードの削除を伴わないためCASCADEに依存しない明示的なUPDATE/DELETEで安全に行う |
| D4 | `VocabQuizMode`は既存どおり「出題形式（カードめくり/4択/入力式）＋方向」を1値に合成した設計のため、単一の`RANDOM_TERM_MEANING`は形式が一意に決まらない。代わりに`FLASH_RANDOM`・`CHOICE_RANDOM`の2値を追加する（入力式は方向が1つしかないため`TYPED_RANDOM`は作らない）。ローカル出題セッション生成時（`vocab.py`の`start_vocab_quiz_session`）で、これらのモードのカードには1問ごとに対応する具体モード（`FLASH_RANDOM`→`FLASH_TERM_TO_MEANING`/`FLASH_MEANING_TO_TERM`、`CHOICE_RANDOM`→`CHOICE_TERM_TO_MEANING`/`CHOICE_MEANING_TO_TERM`）を抽選してから、既存の`_prompt_and_reveal`・`_effective_mode`・`_choice_field`にそのまま渡す | 既存の命名規則（形式プレフィックス＋方向サフィックス）に揃えつつ、既存のモード別分岐・4択誤答生成ロジックを変えずに済む。方向の決定は出題対象のカードを確定した直後、1箇所（新規ヘルパー関数）に集約する（DRYの原則） |
| D5 | `FLASH_RANDOM`・`CHOICE_RANDOM`はTERMカードにのみ設定画面上で選択可能とし、SITUATIONカードが混在するデッキでSITUATIONカードに当たった場合は既存どおり常にFLASH_SITUATIONへ差し替える（`_effective_mode`のフォールバックをそのまま使う）。`CHOICE_RANDOM`選択時の4択可否判定・誤答選択肢プールは既存の`CHOICE_TERM_TO_MEANING`/`CHOICE_MEANING_TO_TERM`と同じ`_CHOICE_MODES`集合に加える | U3の方針どおり、SITUATIONの特別扱いを崩さない。4択の対象・誤答プール制約（F-U3・F-D8）も変えない |
| D6 | 全画面ヘッダー→目標クリックの遷移は、新設の軽量な中継ページ（`VocabGoalQuizRedirectPage`、ルート例：`/vocab/by-goal/:goalId/quiz`）を経由し、`GET /goals/{goalId}/vocab-decks`で取得した1件のデッキIDを使って既存の`/vocab/:deckId/quiz`（`VocabQuizPage`）へ`<Navigate>`する | デッキ単位で作られている既存の出題API・`VocabQuizPage`・`VocabQuizSetupForm`を一切変更せずに再利用できる。バックエンドAPIの変更面を最小化する |
| D7 | 目標詳細の「単語帳」タブ（`VocabDeckListTab.tsx`を置き換え）も同様に、マウント時に`GET /goals/{goalId}/vocab-decks`から1件のデッキIDを解決し、その`deckId`で既存の`VocabDeckAiSection`（AI設定）・`VocabCardList`（カードCRUD）・`VocabImportExportPanel`・`VocabMasteryBreakdownLine`をそのまま描画する | 既存コンポーネントの再利用。新規作成はタブの構成（並び）のみ |
| D8 | 旧`VocabDeckDetailPage`（`/vocab/:deckId`）は、カードCRUD等の中身を持つ画面としては廃止するが、**ルート自体は残し**、中身を「`deck.goal_id`を取得して`ROUTES.goalDetail(goal_id)`へ`<Navigate>`するだけの軽量な中継ページ（`VocabDeckRedirectPage`）」に差し替える。`VocabDeckHeader`・`VocabDeckNameSection`（デッキ名表示・説明文編集・削除ボタン）は削除し、AI設定部分（`VocabDeckAiSection`）のみ目標詳細タブ側へ移植する | `/vocab/:deckId`は`QuizSession.tsx`（今日の復習の解答結果「単語帳で確認する」リンク）・`VocabQuizPage.tsx`・`VocabQuizSummaryView.tsx`の「戻る」リンクから参照され続けている。これらのリンク先コンポーネントを一切変更せずに済むよう、ルートの意味を「デッキ詳細」から「目標詳細への中継」へ変えるだけにとどめ、変更範囲を最小化する（CLAUDE.md「過剰設計を避ける」「最小限の変更」原則） |

## 1. スコープ

- バックエンド：`VocabQuizMode`への方向追加、出題セッション生成ロジックの拡張、目標作成時のデッキ自動生成、既存データの移行マイグレーション
- フロントエンド：`VocabHomePage`の遷移先変更、目標詳細の単語帳タブの中身差し替え、旧デッキ詳細ページ・関連ルートの削除、新設の中継ページ
- 対象外：今日の復習（AI生成・間隔反復）のロジック変更、TERM/SITUATIONの4択・入力式対象範囲の変更、ナレッジエクスポートへの単語帳追加

## 2. 脅威モデル（STRIDE、`/threat-model`スキルに基づく分析）

### 信頼境界

本アプリはローカルWindowsデスクトップで動作する単一ユーザー向けアプリであり、認証情報はサーバー側（開発キットの仕組み）にのみ保持する（CLAUDE.md既定）。したがって「複数ユーザー間の権限分離」は本改修・本アプリ共通のスコープ外である。信頼境界は「フロントエンド（ブラウザ）↔ ローカルFastAPI」の1本のみで、その内側（単一ユーザー自身のデータ）は同一信頼レベルとして扱う。

```
[ユーザー(ブラウザ)] → GET /goals/{goalId}/vocab-decks → deckIdを解決
                     → GET/POST /vocab-decks/{deckId}/... → [SQLite]
[Alembicマイグレーション] → UPDATE vocab_card.deck_id / DELETE vocab_deck → [SQLite]
```

### 脅威と対策（STRIDE）

| 脅威 | カテゴリ | 判定 | 対策・理由 |
| --- | --- | --- | --- |
| 新規認証/認可フローなし | S | Accept | 既存の開発キット認証をそのまま利用、新規の経路を追加しない |
| URLのdeckIdを書き換えて別目標のデッキへ到達 | T/E | Accept | 単一ユーザーローカルアプリのため「他ユーザーのデータ」に該当しない（自分自身の別目標データに過ぎない）。既存の`VocabDeckDetailPage`等も同様にdeckIdを直接受け取る設計であり、本改修が新たに権限境界を弱めるものではない |
| マイグレーションのUPDATE/DELETEが対象外のデッキ・カードへ影響する | T | **Mitigate** | 対象を`WHERE goal_id IN (...)`等の明示的な絞り込みで限定し、複数目標・複数デッキが混在する状態でのテストケース（対象外データが影響を受けないことの確認）を追加する（§3完了条件に反映） |
| マイグレーション失敗時のエラーに内部情報が漏洩 | I | Accept | Alembicログはローカル実行時のみに出力され、既存の運用（他マイグレーションと同様）と同じ |
| マイグレーションのUPDATE/DELETEが大量データで長時間化 | D | Accept | ローカルSQLite・単語帳の登録規模（通常数百〜数千行）では問題にならない想定。レート制限等の追加実装は不要 |
| 新ロール・新権限レベルの導入 | E | Accept | 本改修では導入しない（既存の認証済みローカルユーザー前提のまま） |

### 受容したリスク

- **deckIdのURL直書きによる他目標データへのアクセス可能性**：単一ユーザーローカルアプリのため、別ユーザーとの権限分離は設計上のスコープ外。承認者：利用者（本セッションでの合意、2026-11-26）

## 3. 完了条件（ドラフト）

- [ ] `pytest`（backend）・カバレッジ100%（例外処理を除く）
- [ ] 移行マイグレーションが、複数デッキ所持・デッキ0件・単一デッキの3パターンそれぞれで意図通り動作することをテストで確認
- [ ] 移行マイグレーションが、対象外の目標・デッキ・カード（他のEXAM目標、READING/WORK目標）に影響しないことをテストで確認（脅威モデル§2のMitigate項目）
- [ ] `vitest`（frontend）・カバレッジ100%
- [ ] 旧ルート（`/vocab/:deckId`）・旧コンポーネント（`VocabDeckListTab`等）の参照が残っていないことをgrepで確認（横展開チェック）
- [ ] `ruff check .` / `tsc -b` / lint 0件
- [ ] `docs/CODING_RULES.md`に抵触する文言直書き・重複がないこと
- [ ] `REQUIREMENTS.md`・`SPECIFICATION.md`・`DESIGN.md`（該当箇所）・本書の更新

## 4. 進捗ログ

- 2026-11-26: 本書作成。利用者との対話で0.1節の決定事項を確定。`/threat-model`スキルに基づく脅威分析（§2）を実施し、マイグレーションの絞り込み検証を完了条件へ追加。実装に着手する。
