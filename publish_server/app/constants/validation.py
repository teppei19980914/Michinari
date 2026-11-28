"""アカウント作成・ログインの入力検証定数（CODING_RULES.md 置き場所ルール）。

文字数上限・許可文字種はここへ集約する（CODING_RULES.md DRYの原則）。これらは
D-20（公開APIで受け取るコンテンツの上限）とは別種の、認証入力自体の検証ルールである。
"""

import re

#: ユーザー名はASCII英数字・アンダースコア・ハイフン・ドットのみに制限する。
#: Unicode正規化（NFC/NFD等）の違いで見た目が同じ別アカウントが作られる・既存アカウントに
#: すり替わるリスクをそもそも生じさせないための設計（開発Todo_Web公開_v1.0 単位1テスト観点
#: 「Unicode正規化」）。
USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+$")
USERNAME_MIN_LENGTH = 3
USERNAME_MAX_LENGTH = 64

#: パスワードは任意のUnicode文字を許可するが、ハッシュ化前にNFC正規化する（同じパスワードを
#: 別の正規化形式で入力した場合でも同一パスワードとして扱うため）。上限はargon2-cffiの
#: ハッシュ化コスト（既定パラメータでも入力長に比例して処理時間が伸びる）を利用したDoSを
#: 防ぐための上限。
PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_LENGTH = 256
