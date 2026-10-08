"""ヘルプAIアシスタントの定数（Phase43、開発Todo §4）。

閾値・上限値は `app_setting`、プロンプト文面は `prompt_template` に置く（CODING_RULES.md）。
ここには、プロンプトの書式と検証の仕様として固定する値だけを置く。
"""

import re

#: NewtonX 上のチャットのタイトル。利用者の画面には出さない（開発キット側の表示名）。
HELP_CHAT_TITLE = "ヘルプ質問"

#: 回答の末尾の出典行。プロンプトの「回答の形式」（`prompt_texts.HELP_ASSISTANT`）と
#: 書式を一致させる。
#: 行末にだけ一致させるため、回答本文中の角括弧の語句は出典として扱われない。
CITATION_LINE_PATTERN = re.compile(r"\[出典[:：]\s*([^\]\n]*)\]\s*\Z")

#: 出典行の区切り文字（半角・全角のカンマ、読点）。
CITATION_SEPARATOR_PATTERN = re.compile(r"[,、，]")

#: 質問を区切りの中へ埋め込む前に、山括弧を全角へ置換する。区切り（`<<<QUESTION-...>>>`）を
#: 利用者の質問から偽造できないようにするため（nonce と併用する二重の防御）。
DELIMITER_REPLACEMENTS = str.maketrans({"<": "＜", ">": "＞"})

#: 照合用の正規化で取り除く対象（空白類）。
WHITESPACE_PATTERN = re.compile(r"\s+")

#: 区切りの乱数のバイト数（`secrets.token_hex` に渡す）。
NONCE_BYTES = 8

#: 全文が予算を超えたときに採用するセクションの一致の下限（2文字の組の一致数）。
#: 1件だけの一致は、助詞などの偶然の一致であることが多いため採用しない。
MIN_SECTION_MATCHES = 2
