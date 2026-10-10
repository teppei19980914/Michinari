/** ヘルプAIアシスタントの回答の表示（Phase43）。
 *
 * 回答本文は `MarkdownText` で表示する（生HTMLを解釈しないため、AI生成テキストに含まれる
 * HTML・スクリプトは描画されない）。記載なし・表示できない回答は、AIの文面ではなく
 * `ja.json` の固定文言で示す（開発Todo U2）。 */
import { Link } from 'react-router-dom'
import type { HelpAssistantAnswer } from '../../api/helpAssistant'
import { MarkdownText } from '../../components/MarkdownText'
import { ROUTES } from '../../constants/routes'
import { t } from '../../locales/t'
import { FIXED_STATUS_MESSAGE_KEYS } from './helpAssistantLogic'

/** 固定文言で示す状態（ANSWERED は本文を表示するため含まない）。 */
type FixedStatus = 'NOT_FOUND' | 'UNAVAILABLE'

type HelpAssistantAnswerProps = {
  answer: HelpAssistantAnswer
}

/** 出典（セクションの見出し）の一覧。出典が無い回答では何も出さない。 */
function SectionList({ answer }: HelpAssistantAnswerProps) {
  if (answer.sections.length === 0) return null
  return (
    <p className="mt-2 text-xs text-text-faint">
      {t('helpAssistant.sectionsLabel')}：{answer.sections.map((section) => section.title).join('、')}
    </p>
  )
}

/** 記載なし・表示できない回答。固定文言と、記載なしのときのヘルプ画面への導線。 */
function FixedMessage({ status }: { status: FixedStatus }) {
  return (
    <div className="flex flex-col gap-1">
      <p className="text-sm text-text-secondary">{t(FIXED_STATUS_MESSAGE_KEYS[status])}</p>
      {status === 'NOT_FOUND' && (
        <Link className="text-sm text-accent-muted-text underline" to={ROUTES.help}>
          {t('helpAssistant.helpLink')}
        </Link>
      )}
    </div>
  )
}

/** 回答の本体。本文があるときだけ本文と出典を出し、それ以外は固定文言を出す。
 * 本文が無いのに ANSWERED の回答は、表示できない回答（UNAVAILABLE）として扱う。 */
export function HelpAssistantAnswerBody({ answer }: HelpAssistantAnswerProps) {
  if (answer.status === 'ANSWERED' && answer.answer !== null) {
    return (
      <div>
        <MarkdownText text={answer.answer} className="text-sm text-text-primary" />
        <SectionList answer={answer} />
      </div>
    )
  }
  return <FixedMessage status={answer.status === 'NOT_FOUND' ? 'NOT_FOUND' : 'UNAVAILABLE'} />
}
