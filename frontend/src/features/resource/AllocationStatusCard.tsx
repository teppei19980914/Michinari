import { useQuery } from '@tanstack/react-query'
import { t } from '../../locales/t'
import { Card } from '../../components/Card'
import { getAllocation } from '../../api/resources'
import { QUERY_KEYS } from '../../constants/queryKeys'

/** 配分状況の表示（仕様書6.3「曜日別の総確保時間」「時間枠ごとの各目標への配分時間と残り」
 * 「環境タグ別の時間内訳」）。時間表示はバックエンドで切り捨て済みの値をそのまま出す
 * （換算規則の二重実装を避ける。CLAUDE.md DRYの原則）。 */
export function AllocationStatusCard() {
  const query = useQuery({ queryKey: QUERY_KEYS.resourceAllocation(), queryFn: getAllocation })
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
        <p className="text-sm text-gray-500">{t('resources.allocation.bySlot')}</p>
        <ul className="mt-1 flex flex-col gap-2 text-sm text-gray-700">
          {allocation.slots.map((slot) => (
            <li key={slot.slot_id}>
              <p className={slot.is_over_capacity ? 'text-red-600' : ''}>
                {slot.slot_name}: {slot.allocated_minutes}
                {t('common.unit.minutes')} / {slot.duration_minutes}
                {t('common.unit.minutes')}
                {slot.is_over_capacity
                  ? ` (${t('resources.allocation.overCapacity')})`
                  : ` (${t('resources.allocation.unallocated')}: ${slot.unallocated_minutes}${t('common.unit.minutes')})`}
              </p>
              <ul className="ml-4 text-xs text-gray-500">
                {slot.goal_allocations.length === 0 ? (
                  <li>{t('resources.allocation.noGoals')}</li>
                ) : (
                  slot.goal_allocations.map((goal) => (
                    <li key={goal.goal_id}>
                      {goal.goal_name}: {goal.minutes}
                      {t('common.unit.minutes')}
                    </li>
                  ))
                )}
              </ul>
            </li>
          ))}
        </ul>
      </div>
    </Card>
  )
}
