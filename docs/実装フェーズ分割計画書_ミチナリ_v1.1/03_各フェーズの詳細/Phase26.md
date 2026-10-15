### Phase 26：日次フィードバックAI対話の目標単位分離

| 項目 | 内容 |
| --- | --- |
| 目的 | 分析タブ「成長記述」が全目標のAI日次報告フィードバックを無条件に混在表示する不具合を機に、対症療法（purposeフィルタのみ）ではなく、日次フィードバックの会話そのものを「カテゴリ単位の共有スレッド」から「目標単位」へ分離する根本対応を行う（未決事項L-07の解消方針転換） |
| 投入文書 | CLAUDE.md、運用設計ルール、仕様書（第6.5・6.8節、1.1改15）、設計書 データ構造編（1.1改18）、設計書 ロジック・プロンプト編（23章L-07、1.1改12） |

**実装対象**

- `chat_message`に`goal_id`列を追加（マイグレーション`d8f21a6c4b3e`、NULL許容・FK→goal.id・ondelete=CASCADE）。移行前の行はgoal_id=NULLのまま引き継ぐ
- `daily_feedback_service`・`reading_feedback_service`・`work_feedback_service`を、カテゴリ内の全ACTIVE目標をまとめてプロンプト化する方式から、指定された単一goalのみを扱う方式へ変更（`goal_id`引数を必須化、カテゴリ・ACTIVE状態を検証）。あわせて、選択中でない目標の下書き入力（study_logs/diary_entries等）がプロンプトに混入していた既存の別件バグを修正
- `ai_conversation.ensure_conversation`の呼び出しを`goal=None`から`goal=goal`へ変更し、目標ごとに別会話が作られるようにする
- `ChatRequest`/`ReadingChatRequest`/`WorkChatRequest`に`goal_id`（必須）、`ChatMessageRead`に`goal_id`（NULL許容）を追加
- `GET /analytics/growth-descriptions`を`goal_id`必須化し、指定目標宛て＋同カテゴリの未割り当て（goal_id=NULL）を返す方式に変更。新規`PATCH /analytics/growth-descriptions/{message_id}`を追加し、未割り当てメッセージへの目標の手動割り当てに対応（分析タブ上のプルダウンUI）
- プロンプトテンプレートの「複数目標がある場合の注意」セクションを削除（DAILY_FEEDBACKのみ対象。マイグレーション`c1a5f9e3d7b2`、is_customized=Falseの行のみ更新）
- ナレッジエクスポートの`_build_ai_dialogue`（export_service.py）を、教材のstudy_logがある日付に基づく間接的な絞り込みから`chat_message.goal_id`による直接の絞り込みへ変更し、同日に他目標のAI対話が混入する既存の別件バグを修正
- `DailyReportPage`/`DailyReportViewPage`の送信ペイロード・履歴表示フィルタをgoal_id対応に追随
- `GrowthDescriptionTab`/`AnalyticsPage`を目標単位化し、未割り当てメッセージの目標割り当てUIを追加

**完了条件**

- 同一カテゴリの目標が2件以上同時進行している場合、目標タブを切り替えて送信したAI対話が、選択中の目標以外のタブの対話履歴に表示されない
- 分析タブ「成長記述」で目標を選ぶと、その目標宛ての応答のみが表示される
- 移行前のレガシー応答（goal_id未確定）に対し、分析タブ上のプルダウンから目標を手動で割り当てられる
- ナレッジエクスポートのAI対話履歴に、同日の他目標の対話が混入しない
- 既存のバックエンド・フロントエンドのテストが（前提の変更に伴う書き換えを含め）引き続き成功し、カバレッジ100%を維持する

---

