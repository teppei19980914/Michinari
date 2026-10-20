"""prompt_template: 資格・読書・仕事の週次要約（WEEKLY_SUMMARY・WEEKLY_SUMMARY_READING・
WEEKLY_SUMMARY_WORK）へ{{week_chat}}（週内のAIとの対話のうち利用者本人の発言）を追加する
（S08 G5、開発Todo「S08 要約原則の範囲」v1.0、設計書ロジック・プロンプト編17.3・17.11・17.12
改訂）。

既存のchat_message（AIとの対話）は、これまで週次要約の材料に一度も入っていなかった
（資格=実績＋日記＋集計、読書=想起記録、仕事=業務記録のみ）。要件定義書R-35の原則
（過去の報告内容を漏れなくAIへ入力する）を対話にも及ぼし、利用者が用いた表現・説明の
粒度を保存する対象へ対話中の発言を加える。AIの応答（role=ASSISTANT）は対象外とする
（自己参照の回避、S08決定事項G5-範囲）。既存の生成済み週次要約は作り直さない
（S08決定事項G5-再生成）ため、本マイグレーションはprompt_templateのみを対象とし、
weekly_summaryテーブルのデータには触れない。

Revision ID: 9d3d5631a940
Revises: 0ad4f28cd909
Create Date: 2026-10-20 18:32:44.982456

"""

from datetime import UTC, datetime
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "9d3d5631a940"
down_revision: Union[str, Sequence[str], None] = "0ad4f28cd909"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# app/init/prompt_texts_exam.py のWEEKLY_SUMMARYを一字一句転記したもの（このマイグレーション
# 作成時点のスナップショット）。マイグレーションは実行時点のappコードに依存させないため、
# prompt_textsモジュールをインポートせずここに複製する（0ad4f28cd909と同じ方針）。
_NEW_WEEKLY_SUMMARY_BODY = """以下は、資格試験の学習における一週間分の記録です。
この記録を、後日の振り返りに使えるよう要約してください。

# 対象週
{{week_range}}

# 目標
{{goal_name}}

# 実績
{{week_logs}}

# 集計
{{week_metrics}}

# 日々の記録
{{week_diaries}}

# 本人の発言（AIとの対話）
{{week_chat}}

---

# 要約の要件

この要約は、後日のフィードバック生成時に「過去の経過」として
参照されます。原文は参照されないため、**この要約に含まれない
情報は失われる**ことに留意してください。

以下を必ず含めてください。

1. 学習量と品質の推移（数値を含む）
2. この週に学習した主題と、その理解度に関する記述
   （後日の比較対象となるため、学習者が用いた表現や
     説明の粒度を保存してください。日記に加え、
     AIとの対話中の発言も対象とします）
3. 学習の妨げとなった要因（業務、体調、家庭の事情など、
   記録に現れたもの）
4. 学習者の状態に関する所見（意欲、疲労度、余裕の有無）
5. 前週からの変化
6. 教材の周回が進んだ場合、その事実と切り替えの時期

以下は含めないでください。
- 励ましや評価のコメント
- 今後の提案

これは記録であり、フィードバックではありません。
事実と観察に限定してください。

{{anonymize}}

# 出力形式
簡潔な文章で記述してください。
情報の欠落を避けることを最優先とし、
文章の美しさは考慮しなくて構いません。"""


_OLD_WEEKLY_SUMMARY_BODY = """以下は、資格試験の学習における一週間分の記録です。
この記録を、後日の振り返りに使えるよう要約してください。

# 対象週
{{week_range}}

# 目標
{{goal_name}}

# 実績
{{week_logs}}

# 集計
{{week_metrics}}

# 日々の記録
{{week_diaries}}

---

# 要約の要件

この要約は、後日のフィードバック生成時に「過去の経過」として
参照されます。原文は参照されないため、**この要約に含まれない
情報は失われる**ことに留意してください。

以下を必ず含めてください。

1. 学習量と品質の推移（数値を含む）
2. この週に学習した主題と、その理解度に関する記述
   （後日の比較対象となるため、学習者が用いた表現や
     説明の粒度を保存してください）
3. 学習の妨げとなった要因（業務、体調、家庭の事情など、
   記録に現れたもの）
4. 学習者の状態に関する所見（意欲、疲労度、余裕の有無）
5. 前週からの変化
6. 教材の周回が進んだ場合、その事実と切り替えの時期

以下は含めないでください。
- 励ましや評価のコメント
- 今後の提案

これは記録であり、フィードバックではありません。
事実と観察に限定してください。

{{anonymize}}

# 出力形式
簡潔な文章で記述してください。
情報の欠落を避けることを最優先とし、
文章の美しさは考慮しなくて構いません。"""


# app/init/prompt_texts_reading.py のWEEKLY_SUMMARY_READINGを一字一句転記したもの。
_NEW_WEEKLY_SUMMARY_READING_BODY = """以下は、読書における一週間分の想起記録です。
この記録を、後日の振り返りに使えるよう要約してください。

# 対象週
{{week_range}}

# 書籍
{{book_title}}

# 想起記録
{{week_recalls}}

# 本人の発言（AIとの対話）
{{week_chat}}

---

# 要約の要件

この要約は、後日の日次報告フィードバック・読了レポートの
生成時に「過去の経過」として参照されます。原文は参照されないため、
**この要約に含まれない情報は失われる**ことに留意してください。

以下を必ず含めてください。

1. この週に読んだ内容として記録された事実
2. 感じたこと・考えたこと（読者が用いた表現や
   説明の粒度を保存してください。想起記録に加え、
   AIとの対話中の発言も対象とします）
3. 気づき（「気づいた」「初めて分かった」に相当する記述）
4. 前週からの考えの変化（記録に現れた場合）

以下は含めないでください。
- ページ数や読了ペースに関する評価
- 励ましや評価のコメント
- 今後の提案

これは記録であり、フィードバックではありません。
事実と記録された感想に限定してください。

{{anonymize}}

# 出力形式
簡潔な文章で記述してください。
情報の欠落を避けることを最優先とし、
文章の美しさは考慮しなくて構いません。"""


_OLD_WEEKLY_SUMMARY_READING_BODY = """以下は、読書における一週間分の想起記録です。
この記録を、後日の振り返りに使えるよう要約してください。

# 対象週
{{week_range}}

# 書籍
{{book_title}}

# 想起記録
{{week_recalls}}

---

# 要約の要件

この要約は、後日の日次報告フィードバック・読了レポートの
生成時に「過去の経過」として参照されます。原文は参照されないため、
**この要約に含まれない情報は失われる**ことに留意してください。

以下を必ず含めてください。

1. この週に読んだ内容として記録された事実
2. 感じたこと・考えたこと（読者が用いた表現や
   説明の粒度を保存してください）
3. 気づき（「気づいた」「初めて分かった」に相当する記述）
4. 前週からの考えの変化（記録に現れた場合）

以下は含めないでください。
- ページ数や読了ペースに関する評価
- 励ましや評価のコメント
- 今後の提案

これは記録であり、フィードバックではありません。
事実と記録された感想に限定してください。

{{anonymize}}

# 出力形式
簡潔な文章で記述してください。
情報の欠落を避けることを最優先とし、
文章の美しさは考慮しなくて構いません。"""


# app/init/prompt_texts_work.py のWEEKLY_SUMMARY_WORKを一字一句転記したもの。
_NEW_WEEKLY_SUMMARY_WORK_BODY = """以下は、仕事における一週間分の業務記録です。
この記録を、後日の振り返りに使えるよう要約してください。

# 対象週
{{week_range}}

# 案件
{{work_name}}

# 業務記録
{{week_logs}}

# 本人の発言（AIとの対話）
{{week_chat}}

---

# 要約の要件

この要約は、後日の日次報告フィードバック・月次報告・半期評価の
生成時に「過去の経過」として参照されます。原文は参照されないため、
**この要約に含まれない情報は失われる**ことに留意してください。

以下を必ず含めてください。

1. この週に取り組んだ業務内容（時系列またはテーマ別）
2. 工夫や粘り強さが記述されている場合はその内容
   （成果の評価ではなく、プロセスの記録として。
     業務記録に加え、AIとの対話中の発言も対象とします）
3. 業務の妨げとなった要因（記録に現れたもの）
4. 前週からの変化

以下は含めないでください。
- ノルマの達成度や生産性の評価
- 励ましや評価のコメント
- 今後の提案

これは記録であり、フィードバックではありません。
事実と記録された内容に限定してください。

{{anonymize}}

# 出力形式
簡潔な文章で記述してください。
情報の欠落を避けることを最優先とし、
文章の美しさは考慮しなくて構いません。"""


_OLD_WEEKLY_SUMMARY_WORK_BODY = """以下は、仕事における一週間分の業務記録です。
この記録を、後日の振り返りに使えるよう要約してください。

# 対象週
{{week_range}}

# 案件
{{work_name}}

# 業務記録
{{week_logs}}

---

# 要約の要件

この要約は、後日の日次報告フィードバック・月次報告・半期評価の
生成時に「過去の経過」として参照されます。原文は参照されないため、
**この要約に含まれない情報は失われる**ことに留意してください。

以下を必ず含めてください。

1. この週に取り組んだ業務内容（時系列またはテーマ別）
2. 工夫や粘り強さが記述されている場合はその内容
   （成果の評価ではなく、プロセスの記録として）
3. 業務の妨げとなった要因（記録に現れたもの）
4. 前週からの変化

以下は含めないでください。
- ノルマの達成度や生産性の評価
- 励ましや評価のコメント
- 今後の提案

これは記録であり、フィードバックではありません。
事実と記録された内容に限定してください。

{{anonymize}}

# 出力形式
簡潔な文章で記述してください。
情報の欠落を避けることを最優先とし、
文章の美しさは考慮しなくて構いません。"""


def _prompt_template_table() -> sa.Table:
    return sa.table(
        "prompt_template",
        sa.column("purpose", sa.String),
        sa.column("body", sa.Text),
        sa.column("is_customized", sa.Boolean),
        sa.column("updated_at", sa.DateTime),
    )


_PURPOSE_BODIES = (
    ("WEEKLY_SUMMARY", _NEW_WEEKLY_SUMMARY_BODY, _OLD_WEEKLY_SUMMARY_BODY),
    ("WEEKLY_SUMMARY_READING", _NEW_WEEKLY_SUMMARY_READING_BODY, _OLD_WEEKLY_SUMMARY_READING_BODY),
    ("WEEKLY_SUMMARY_WORK", _NEW_WEEKLY_SUMMARY_WORK_BODY, _OLD_WEEKLY_SUMMARY_WORK_BODY),
)


def upgrade() -> None:
    """Upgrade schema.

    資格・読書・仕事の週次要約へ{{week_chat}}を追加する（S08 G5）。0ad4f28cd909・
    f7c3e9a1b5d6と同じくis_customized=False（利用者が未編集）の行のみを対象とし、
    利用者が編集済みのテンプレートは上書きしない（新変数は注入されないまま残る）。
    """
    bind = op.get_bind()
    prompt_template = _prompt_template_table()
    now = datetime.now(UTC)
    for purpose, new_body, _old_body in _PURPOSE_BODIES:
        bind.execute(
            prompt_template.update()
            .where(
                prompt_template.c.purpose == purpose,
                prompt_template.c.is_customized.is_(False),
            )
            .values(body=new_body, updated_at=now)
        )


def downgrade() -> None:
    """Downgrade schema.

    {{week_chat}}を含まない旧文面へ戻す。upgrade同様、is_customized=Falseの行のみ対象とする。
    """
    bind = op.get_bind()
    prompt_template = _prompt_template_table()
    now = datetime.now(UTC)
    for purpose, _new_body, old_body in _PURPOSE_BODIES:
        bind.execute(
            prompt_template.update()
            .where(
                prompt_template.c.purpose == purpose,
                prompt_template.c.is_customized.is_(False),
            )
            .values(body=old_body, updated_at=now)
        )
