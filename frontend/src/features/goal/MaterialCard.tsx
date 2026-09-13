/** 教材タブ（MaterialsTab.tsx）の1件分の表示カード。
 *
 * 1関数100行の上限（CODING_RULES.md「保守性（複雑度）」）を超えていた MaterialsTab から、
 * 編集中でない教材の表示と操作ボタンを切り出したものである。削除・停止の実行そのものは
 * 呼び出し元のミューテーションが担い、ここは押されたことを伝えるだけに徹する。 */
import { useQuery } from '@tanstack/react-query'
import { formatPercent } from '../../utils/format'
import { t } from '../../locales/t'
import { Card } from '../../components/Card'
import { Button } from '../../components/Button'
import { apiClient } from '../../api/client'
import type { MaterialRead } from '../../api/goals'
import type { components } from '../../types/api.d.ts'
import { QUERY_KEYS } from '../../constants/queryKeys'

type SlotCheckRead = components['schemas']['SlotCheckRead']

/** その教材が時間枠に収まらない場合だけ警告を出す（収まる場合・未取得の場合は何も出さない）。 */
function SlotCheckWarning({ materialId }: { materialId: number }) {
  const query = useQuery({
    queryKey: QUERY_KEYS.materialSlotCheck(materialId),
    queryFn: () => apiClient.get<SlotCheckRead>(`/materials/${materialId}/slot-check`),
  })
  if (!query.data || query.data.sufficient) {
    return null
  }
  return (
    <p className="mt-1 text-xs text-amber-700">{t('goals.materials.slotInsufficientWarning')}</p>
  )
}

export function MaterialCard({
  material,
  readOnly,
  onEdit,
  onDeactivate,
  onDelete,
}: {
  material: MaterialRead
  readOnly: boolean
  onEdit: () => void
  onDeactivate: () => void
  onDelete: () => void
}) {
  return (
    <Card>
      <div className="flex items-start justify-between">
        <div>
          <p className="font-medium text-gray-900">{material.name}</p>
          <dl className="mt-1 grid grid-cols-2 gap-x-4 gap-y-1 text-sm text-gray-600 sm:grid-cols-4">
            <div>
              <dt className="text-gray-400">{t('goals.materials.totalWork')}</dt>
              <dd>
                {material.total_work}
                {material.unit_label}
              </dd>
            </div>
            <div>
              <dt className="text-gray-400">{t('goals.materials.currentCycle')}</dt>
              <dd>
                {t('goals.materials.cycleLabel', {
                  current: material.current_cycle,
                  planned: material.planned_cycles,
                })}
              </dd>
            </div>
            <div>
              <dt className="text-gray-400">{t('goals.materials.cycleProgress')}</dt>
              <dd>{formatPercent(material.progress_rate_in_cycle)}</dd>
            </div>
            <div>
              <dt className="text-gray-400">{t('goals.materials.overallProgress')}</dt>
              <dd>{formatPercent(material.progress_rate)}</dd>
            </div>
          </dl>
          <SlotCheckWarning materialId={material.id} />
        </div>
        {!readOnly && (
          <div className="flex flex-col gap-2">
            <Button variant="secondary" onClick={onEdit}>
              {t('common.action.edit')}
            </Button>
            {material.is_active && (
              <Button variant="secondary" onClick={onDeactivate}>
                {t('goals.materials.deactivate')}
              </Button>
            )}
            <Button variant="secondary" onClick={onDelete}>
              {t('common.action.delete')}
            </Button>
          </div>
        )}
      </div>
    </Card>
  )
}
