"""目標相談チャットの定数（S09、開発Todo §4）。

閾値・上限値は `app_setting`、プロンプト文面は `prompt_template` に置く（CODING_RULES.md）。
ここには、プロンプトの書式と検証の仕様として固定する値だけを置く
（`app/constants/help_assistant.py`と同じ役割分担）。
"""

import re

#: NewtonX 上のチャットのタイトル。利用者の画面には出さない（開発キット側の表示名）。
GOAL_CONSULTATION_CHAT_TITLE = "目標相談"

#: 回答末尾の根拠行から、個々の根拠（記録の日付／週次要約の週）を取り出す。
#: 行末にだけ一致させるため、本文中の角括弧の語句は根拠として扱われない。
RECORD_CITATION_PATTERN = re.compile(r"\[記録:\s*(\d{4}-\d{2}-\d{2})\]")
SUMMARY_CITATION_PATTERN = re.compile(r"\[要約:\s*(\d{4}-\d{2}-\d{2})\s*〜\s*(\d{4}-\d{2}-\d{2})\]")

#: 根拠行全体（末尾の連続した根拠括弧、または「根拠なし」の1個）に一致させる。
#: 本文と根拠行を分離するために使う（ヘルプのCITATION_LINE_PATTERNと同じ考え方）。
CITATION_TRAILER_PATTERN = re.compile(
    r"(?:\s*\[(?:記録:\s*\d{4}-\d{2}-\d{2}|要約:\s*\d{4}-\d{2}-\d{2}\s*〜\s*\d{4}-\d{2}-\d{2})\])+\s*\Z"
    r"|\s*\[根拠:\s*なし\]\s*\Z"
)

#: 質問を区切りの中へ埋め込む前に、山括弧を全角へ置換する（ヘルプと同じ二重の防御）。
DELIMITER_REPLACEMENTS = str.maketrans({"<": "＜", ">": "＞"})

#: 照合用の正規化で取り除く対象（空白類）。禁止語判定の正規化に使う（ヘルプと共通の方式）。
WHITESPACE_PATTERN = re.compile(r"\s+")

#: 区切りの乱数のバイト数（`secrets.token_hex` に渡す）。
NONCE_BYTES = 8
