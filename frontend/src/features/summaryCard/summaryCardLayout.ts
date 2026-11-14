import { t } from '../../locales/t'
import type { SummaryCardRead } from '../../api/summaryCard'
import { resolveMilestoneMessage } from '../milestone/milestoneContent'
import type { SummaryCardVisibility } from './summaryCardVisibility'

export type SummaryCardTextLine =
  | { key: 'recordDays'; label: string; value: string }
  | { key: 'longestConsecutiveDays'; label: string; value: string }
  | { key: 'topTheme'; label: string; value: string }
  | { key: 'milestones'; label: string; values: string[] }
  | { key: 'aiSentence'; label: string; value: string }

/** カードの文字情報の行を組み立てる（道のりマップ縮小図は別枠でSummaryCardPreviewが描く）。
 * データが無い項目（WORKのテーマ、未達成の節目、未生成のAI一文）は表示トグルの値に
 * かかわらず出力しない（仕様書6.10「カード内容」）。 */
export function buildSummaryCardTextLines(params: {
  aggregate: SummaryCardRead
  visibility: SummaryCardVisibility
  sentence: string | null
}): SummaryCardTextLine[] {
  const { aggregate, visibility, sentence } = params
  const lines: SummaryCardTextLine[] = []

  if (visibility.recordDays) {
    lines.push({
      key: 'recordDays',
      label: t('summaryCard.labels.recordDays'),
      value: t('summaryCard.unit.days', { count: aggregate.record_days }),
    })
  }
  if (visibility.longestConsecutiveDays) {
    lines.push({
      key: 'longestConsecutiveDays',
      label: t('summaryCard.labels.longestConsecutiveDays'),
      value: t('summaryCard.unit.days', { count: aggregate.longest_consecutive_days }),
    })
  }
  if (visibility.topTheme && aggregate.top_theme_name !== null) {
    lines.push({
      key: 'topTheme',
      label: t('summaryCard.labels.topTheme'),
      value: aggregate.top_theme_name,
    })
  }
  if (visibility.milestones && aggregate.milestones.length > 0) {
    lines.push({
      key: 'milestones',
      label: t('summaryCard.labels.milestones'),
      values: aggregate.milestones.map((milestone) => resolveMilestoneMessage(milestone)),
    })
  }
  if (visibility.aiSentence && sentence !== null) {
    lines.push({
      key: 'aiSentence',
      label: t('summaryCard.labels.aiSentence'),
      value: sentence,
    })
  }
  return lines
}
