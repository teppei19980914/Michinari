import { useQuery } from '@tanstack/react-query'
import { dateTimeLocaleTag, t } from '../../locales/t'
import { Card } from '../../components/Card'
import { apiErrorMessage } from '../../api/client'
import { listMilestones } from '../../api/milestones'
import { CHARACTER_ICONS } from '../../constants/characterIcons'
import { QUERY_KEYS } from '../../constants/queryKeys'
import type { GoalCategory } from '../../api/goals'
import { resolveMilestoneIcon, resolveMilestoneMessage } from '../milestone/milestoneContent'

type MilestoneListTabProps = { goalId: number; category: GoalCategory }

/** 分析画面「節目の記録」タブ（開発Todo_節目のお祝い_v1.0 M10）。ダッシュボードには置かず
 * （初期表示2秒以内の性能要件を避ける）、振り返り用途の分析画面へ置く。到達の新しい順に
 * 一覧表示する（お祝い済み・未済を問わない）。 */
export function MilestoneListTab({ goalId, category }: MilestoneListTabProps) {
  const query = useQuery({
    queryKey: QUERY_KEYS.goalMilestones(goalId),
    queryFn: () => listMilestones(goalId),
  })

  if (query.isLoading) {
    return <p className="text-sm text-text-faint">{t('common.loading')}</p>
  }
  if (query.isError || !query.data) {
    return <p className="text-sm text-danger-text">{apiErrorMessage(query.error)}</p>
  }
  if (query.data.length === 0) {
    return <p className="text-sm text-text-faint">{t('milestone.list.empty')}</p>
  }

  return (
    <div className="flex flex-col gap-3">
      {query.data.map((achievement) => (
        <Card key={achievement.id} className="flex items-center gap-3">
          <img
            src={CHARACTER_ICONS[resolveMilestoneIcon(category)]}
            alt=""
            className="h-10 w-10 flex-none"
          />
          <div>
            <p className="text-sm text-text-primary">{resolveMilestoneMessage(achievement)}</p>
            <p className="mt-1 text-xs text-text-disabled">
              {t('milestone.list.achievedAt', {
                date: new Date(achievement.achieved_at).toLocaleString(dateTimeLocaleTag()),
              })}
            </p>
          </div>
        </Card>
      ))}
    </div>
  )
}
