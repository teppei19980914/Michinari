import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { t } from '../locales/t'
import { apiErrorMessage } from '../api/client'
import { ROUTES } from '../constants/routes'
import { getGoal, listGoals } from '../api/goals'
import { ReadingLogHistoryTab } from '../features/analytics/ReadingLogHistoryTab'
import { GrowthDescriptionTab } from '../features/analytics/GrowthDescriptionTab'
import { RetrospectiveSection } from '../features/export/RetrospectiveSection'
import { BookInfoTab } from '../features/bookshelf/BookInfoTab'
import { QUERY_KEYS } from '../constants/queryKeys'

const TABS = [
  { key: 'info', labelKey: 'bookshelf.detail.tabs.info' },
  { key: 'log', labelKey: 'bookshelf.detail.tabs.log' },
  { key: 'growth', labelKey: 'bookshelf.detail.tabs.growth' },
  { key: 'retrospective', labelKey: 'bookshelf.detail.tabs.retrospective' },
] as const

type TabKey = (typeof TABS)[number]['key']

/** SC-19 書籍詳細。本棚（SC-18）から選んだ1冊について、日次の想起記録・成長記述・
 * 振り返りレポートをタブで閲覧する閲覧専用画面(アーカイブ操作はSC-18側に集約する)。 */
export function BookDetailPage() {
  const { goalId: goalIdParam } = useParams<{ goalId: string }>()
  const goalId = Number(goalIdParam)
  const [tab, setTab] = useState<TabKey>('info')

  const goalQuery = useQuery({ queryKey: QUERY_KEYS.goal(goalId), queryFn: () => getGoal(goalId) })
  const goalsQuery = useQuery({ queryKey: QUERY_KEYS.goals(), queryFn: listGoals })

  if (goalQuery.isLoading || goalsQuery.isLoading) {
    return <p className="p-6 text-sm text-gray-500">{t('common.loading')}</p>
  }
  if (goalQuery.isError || !goalQuery.data || goalsQuery.isError || !goalsQuery.data) {
    return <p className="p-6 text-sm text-red-600">{apiErrorMessage(goalQuery.error)}</p>
  }

  const goal = goalQuery.data
  const book = goal.book
  if (goal.category !== 'READING' || book === null || book === undefined) {
    return <p className="p-6 text-sm text-gray-500">{t('bookshelf.detail.notReadingGoal')}</p>
  }

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-4 p-4">
      <Link to={ROUTES.bookshelf} className="text-sm text-blue-600 hover:underline">
        {t('bookshelf.detail.backLink')}
      </Link>

      <div className="flex flex-wrap gap-1 border-b border-gray-200">
        {TABS.map((item) => (
          <button
            key={item.key}
            type="button"
            onClick={() => setTab(item.key)}
            className={`px-3 py-2 text-sm font-medium ${
              tab === item.key
                ? 'border-b-2 border-blue-600 text-blue-700'
                : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            {t(item.labelKey)}
          </button>
        ))}
      </div>

      {tab === 'info' && <BookInfoTab book={book} goal={goal} />}
      {tab === 'log' && <ReadingLogHistoryTab goalId={goalId} />}
      {tab === 'growth' && <GrowthDescriptionTab goalId={goalId} goals={goalsQuery.data} />}
      {tab === 'retrospective' && (
        // 本棚は個人が見返すための閲覧専用画面であり、匿名化はエクスポート（SC-13）専用の
        // 関心事のためトグルUIを持たず常に非匿名で表示する（仕様書6.17）。
        <RetrospectiveSection goalId={goalId} anonymize={false} isReading={true} />
      )}
    </div>
  )
}
