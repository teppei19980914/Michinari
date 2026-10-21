/** 目標相談チャットの回答の表示（S09）。
 *
 * 回答本文は`MarkdownText`で表示する（生HTMLを解釈しないため、AI生成テキストに含まれる
 * HTML・スクリプトは描画されない）。根拠の日付は、その日の日次報告の閲覧画面へのリンクに
 * する（開発Todo U11）。週次要約の根拠は週単位の閲覧画面が無いため文字表示のみ。 */
import { Link } from 'react-router-dom'
import type { GoalConsultationAnswer } from '../../api/goalConsultation'
import { MarkdownText } from '../../components/MarkdownText'
import { ROUTES } from '../../constants/routes'
import { t } from '../../locales/t'
import { UNAVAILABLE_MESSAGE_KEY } from './goalConsultationLogic'

type GoalConsultationAnswerProps = {
  answer: GoalConsultationAnswer
}

/** 根拠（日付・週）の一覧。根拠が無い回答では何も出さない。 */
function CitationList({ answer }: GoalConsultationAnswerProps) {
  if (answer.cited_dates.length === 0 && answer.cited_weeks.length === 0) return null
  return (
    <p className="mt-2 flex flex-wrap gap-2 text-xs text-text-faint">
      <span>{t('goalConsultation.citationsLabel')}：</span>
      {answer.cited_dates.map((date) => (
        <Link key={date} className="text-accent-muted-text underline" to={ROUTES.dailyReportView(date)}>
          {date}
        </Link>
      ))}
      {answer.cited_weeks.map((week) => (
        <span key={`${week.start}-${week.end}`}>
          {week.start}〜{week.end}
        </span>
      ))}
    </p>
  )
}

/** 回答の本体。本文があるときだけ本文と根拠を出し、それ以外は固定文言を出す。
 * 本文が無いのにANSWEREDの回答は、表示できない回答（UNAVAILABLE）として扱う。 */
export function GoalConsultationAnswerBody({ answer }: GoalConsultationAnswerProps) {
  if (answer.status === 'ANSWERED' && answer.answer !== null) {
    return (
      <div>
        <MarkdownText text={answer.answer} className="text-sm text-text-primary" />
        <CitationList answer={answer} />
      </div>
    )
  }
  return <p className="text-sm text-text-secondary">{t(UNAVAILABLE_MESSAGE_KEY)}</p>
}
