import { t } from '../../locales/t'
import { Card } from '../../components/Card'
import type { DashboardRead } from '../../api/dashboard'

type TodayQuotaSectionProps = {
  todayQuota: DashboardRead['today_quota']
  availableSlotNames: DashboardRead['available_slot_names']
  isBufferDay: boolean
}

/** 本日のノルマ（仕様書6.1「進行中の全教材について、目標分量・目標時間・
 * 使用予定スロット・現在周回を一覧」）。 */
export function TodayQuotaSection({
  todayQuota,
  availableSlotNames,
  isBufferDay,
}: TodayQuotaSectionProps) {
  return (
    <Card>
      <h2 className="mb-2 font-medium text-gray-900">{t('dashboard.todayQuota.title')}</h2>
      {isBufferDay && (
        <p className="mb-2 text-sm text-amber-700">{t('dashboard.todayQuota.bufferDayNotice')}</p>
      )}
      {todayQuota.length === 0 ? (
        <p className="text-sm text-gray-500">{t('dashboard.todayQuota.empty')}</p>
      ) : (
        <ul className="divide-y divide-gray-100">
          {todayQuota.map((item) => (
            <li key={item.material_id} className="flex items-center justify-between py-2 text-sm">
              <div>
                <p className="text-gray-900">{item.material_name}</p>
                <p className="text-gray-500">
                  {t('dashboard.todayQuota.cycleLabel', {
                    current: item.current_cycle,
                    planned: item.planned_cycles,
                  })}
                </p>
              </div>
              <div className="text-right text-gray-700">
                <p>
                  {isBufferDay ? 0 : Math.round(item.daily_quota * 10) / 10}
                  {item.unit_label}
                </p>
                <p className="text-gray-500">
                  {item.target_minutes === null || isBufferDay
                    ? t('dashboard.todayQuota.targetMinutesUnavailable')
                    : `${Math.round(item.target_minutes)}${t('common.unit.minutes')}`}
                </p>
              </div>
            </li>
          ))}
        </ul>
      )}
      {availableSlotNames.length > 0 && (
        <p className="mt-3 text-xs text-gray-500">
          {t('dashboard.todayQuota.availableSlots')}: {availableSlotNames.join('、')}
        </p>
      )}
    </Card>
  )
}
