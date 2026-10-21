"""ヘルプAIアシスタントの定数（Phase43、開発Todo §4）。

閾値・上限値は `app_setting`、プロンプト文面は `prompt_template` に置く（CODING_RULES.md）。
ここには、プロンプトの書式と検証の仕様として固定する値だけを置く。
利用者の自由入力の安全対策（区切りの全角化・禁止語照合の正規化・nonceの桁数）はヘルプ専用の
値ではなく、目標相談チャット（S09）とも共有するため `app/ai/question_safety.py` に集約する
（CODING_RULES.md DRYの原則）。
"""

import re

#: NewtonX 上のチャットのタイトル。利用者の画面には出さない（開発キット側の表示名）。
HELP_CHAT_TITLE = "ヘルプ質問"

#: 回答の末尾の出典行。プロンプトの「回答の形式」（`prompt_texts_common.HELP_ASSISTANT`）と
#: 書式を一致させる。
#: 行末にだけ一致させるため、回答本文中の角括弧の語句は出典として扱われない。
CITATION_LINE_PATTERN = re.compile(r"\[出典[:：]\s*([^\]\n]*)\]\s*\Z")

#: 出典行の区切り文字（半角・全角のカンマ、読点）。
CITATION_SEPARATOR_PATTERN = re.compile(r"[,、，]")

#: 全文が予算を超えたときに採用するセクションの一致の下限（2文字の組の一致数）。
#: 1件だけの一致は、助詞などの偶然の一致であることが多いため採用しない。
MIN_SECTION_MATCHES = 2
