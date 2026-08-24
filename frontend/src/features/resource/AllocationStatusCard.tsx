import { useQuery } from '@tanstack/react-query'
import { t } from '../../locales/t'
import { Card } from '../../components/Card'
import { formatPercent } from '../../utils/format'
import { getAllocation } from '../../api/resources'

/** 配分状況の表示（仕様書6.3「曜日別の総確保時間」「各目標への配分状況と未配分の残量」
 * 「環境タグ別の時間内訳」）。 */
export function AllocationStatusCard() {
  const query = useQuery({ queryKey: ['resource-allocation'], queryFn: getAllocation })
  if (!query.data) {
    return null
  }
  const allocation = query.data

  return (
    <Card className="flex flex-col gap-3">
      <h2 className="font-medium text-gray-900">{t('resources.allocation.title')}</h2>

      <div>
        <p className="text-sm text-gray-500">{t('resources.allocation.byWeekday')}</p>
        <div className="mt-1 flex flex-wrap gap-3 text-sm text-gray-700">
          {Object.entries(allocation.total_hours_by_weekday).map(([weekday, hours]) => (
            <span key={weekday}>
              {t(`resources.weekdays.${weekday}`)}: {hours}
              {t('common.unit.hours')}
            </span>
          ))}
        </div>
      </div>

      <div>
        <p className="text-sm text-gray-500">{t('resources.allocation.byEnvironment')}</p>
        <div className="mt-1 flex flex-wrap gap-3 text-sm text-gray-700">
          {Object.entries(allocation.total_hours_by_environment).map(([env, hours]) => (
            <span key={env}>
              {t(`goals.materials.environment.${env}`)}: {hours}
              {t('common.unit.hours')}
            </span>
          ))}
        </div>
      </div>

      <div>
        <p className="text-sm text-gray-500">{t('resources.allocation.byGoal')}</p>
        <ul className="mt-1 text-sm text-gray-700">
          {allocation.goal_allocations.map((goal) => (
            <li key={goal.goal_id}>
              {goal.goal_name}: {formatPercent(goal.resource_ratio)}
            </li>
          ))}
        </ul>
        <p className="mt-1 text-sm text-gray-500">
          {t('resources.allocation.unallocated')}: {formatPercent(allocation.unallocated_ratio)}
        </p>
      </div>
    </Card>
  )
}
