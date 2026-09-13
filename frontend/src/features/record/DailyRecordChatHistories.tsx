/** 日次報告閲覧（SC-08 DailyReportViewPage）のAI対話履歴。
 *
 * 1関数100行の上限（CODING_RULES.md「保守性（複雑度）」）への対応で、カテゴリごとに
 * 逐語で3回書かれていたカードを1つにまとめたものである（CLAUDE.md DRYの原則）。
 * どの履歴を出すかの判定は dailyReportViewSections.ts が担い、ここは受け取った分を
 * 並べるだけに徹する。 */
import { t } from '../../locales/t'
import { Card } from '../../components/Card'
import { ChatPanel } from './ChatPanel'
import type { ChatHistorySection } from './dailyReportViewSections'

export function DailyRecordChatHistories({ histories }: { histories: ChatHistorySection[] }) {
  return (
    <>
      {histories.map((history) => (
        <Card key={history.key} className="flex flex-col gap-2">
          <h2 className="font-medium text-gray-900">{t(history.titleKey)}</h2>
          <ChatPanel messages={history.messages} readOnly />
        </Card>
      ))}
    </>
  )
}
