"""app_setting テーブルに存在しないドメイン定数。

設計書 データ構造編 5.2 の初期投入キー一覧には含まれておらず、将来のチューニング対象として
未決事項に残されている値（ロジック・プロンプト編 21章）。設定画面から変更する対象ではないため
app_setting ではなくここに集約し、複数ファイルへの直書きを避ける。
"""

from app.constants.enums import AiPurpose

# 実効速度の算出に必要なサンプル数下限（ロジック・プロンプト編 8.2、未決事項 L-03）。
MIN_SPEED_SAMPLE_COUNT = 3

# 完了予測日の反復打ち切り日数（ロジック・プロンプト編 10.1）。
FORECAST_ITERATION_CAP_DAYS = 365

# プロンプト縮退の段階4（日記の先頭からの切り詰め）で1回に削る文字数
# （ロジック・プロンプト編 16.5）。縮退アルゴリズムの内部実装値であり、
# ai.max_prompt_chars のような利用者が調整する閾値ではないためapp_settingの対象外とする。
PROMPT_DIARY_TRIM_CHUNK_CHARS = 200

# 「AIが参照した情報」（非エンジニア向け、AI対話の送信内容を種別で示す機能）で用途ごとに
# 返すカテゴリ集合。プロンプトは常に全項目を埋め込む設計（データが無くても「まだ〜
# ありません」という文言が入る、app/ai/prompt_builder.py）ため、実際の値を都度見て動的に
# 判定するのではなく、用途固定のリストとする。フロントではロケールキー
# （frontend/src/locales/ja.json の chat.contextCategories.*）へ変換して一覧表示する。
CONTEXT_CATEGORIES_BY_PURPOSE: dict[AiPurpose, list[str]] = {
    AiPurpose.DAILY_FEEDBACK: [
        "GOAL_INFO",
        "TODAY_RECORD",
        "WEEKLY_SUMMARY",
        "MATERIAL_PROGRESS",
    ],
    AiPurpose.DAILY_FEEDBACK_READING: ["GOAL_INFO", "TODAY_RECORD", "WEEKLY_SUMMARY"],
    AiPurpose.DAILY_FEEDBACK_WORK: ["GOAL_INFO", "TODAY_RECORD", "WEEKLY_SUMMARY"],
}
