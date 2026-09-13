import { t } from '../../locales/t'
import { StudyLogCard } from './StudyLogCard'
import type { SlotMinutesFormValue } from './slotMinutesForm'
import type { StudyLogFormValue } from './studyLogForm'
import type { QuotaItemRead } from '../../api/records'
import { groupByGoal } from '../../utils/groupByGoal'

type StudyLogFieldsProps = {
  quotaItems: QuotaItemRead[]
  values: Record<number, StudyLogFormValue>
  onChangeField: (materialId: number, field: keyof StudyLogFormValue, value: string) => void
  /** 時間枠ごとの投下時間の変更（仕様書6.5）。 */
  onChangeSlotMinutes: (materialId: number, slotMinutes: SlotMinutesFormValue) => void
  /** 追加候補の全時間枠（slot_id → 名称）。「他の時間枠を追加」で使う。 */
  slotNames: Map<number, string>
  /** SC-07専用: 投下時間が任意入力である旨を明示する（仕様書6.6）。 */
  showMinutesOptionalNotice?: boolean
}

/** 実績入力欄（教材別の投下時間・完了分量・周回・品質指標）。SC-06/SC-07で共有する
 * （仕様書6.5・6.6は同一の入力表を前提としており、CLAUDE.md DRYの原則に従い共通化する）。
 *
 * 教材1件分の入力欄は StudyLogCard.tsx へ切り出してある（CODING_RULES.md「保守性
 * （複雑度）」）。この関数は「出すかどうか」と目標ごとのグルーピングを担う。 */
export function StudyLogFields({
  quotaItems,
  values,
  onChangeField,
  onChangeSlotMinutes,
  slotNames,
  showMinutesOptionalNotice = false,
}: StudyLogFieldsProps) {
  if (quotaItems.length === 0) {
    return <p className="text-sm text-gray-500">{t('dailyReport.studyLog.empty')}</p>
  }

  const goalGroups = groupByGoal(quotaItems)

  return (
    <div className="flex flex-col gap-3">
      {goalGroups.map((group) => (
        <div key={group.goalId} className="flex flex-col gap-3">
          {goalGroups.length > 1 && (
            <h3 className="font-medium text-gray-900">{group.goalName}</h3>
          )}
          {group.items.map((item) => {
            const value = values[item.material_id]
            // 値が未初期化の教材は描画しない（入力欄が非制御へ切り替わってしまうため）。
            if (!value) {
              return null
            }
            return (
              <StudyLogCard
                key={item.material_id}
                item={item}
                value={value}
                slotNames={slotNames}
                onChangeField={onChangeField}
                onChangeSlotMinutes={onChangeSlotMinutes}
              />
            )
          })}
        </div>
      ))}
      {showMinutesOptionalNotice && (
        <p className="text-xs text-gray-500">{t('progressOnly.minutesOptionalNotice')}</p>
      )}
    </div>
  )
}
