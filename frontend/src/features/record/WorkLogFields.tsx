import { t } from '../../locales/t'
import { Card } from '../../components/Card'
import { Textarea } from '../../components/Textarea'
import type { WorkAssignmentRead } from '../../api/goals'
import type { WorkLogFormValue } from './workLogForm'

type WorkLogFieldsProps = {
  workAssignments: WorkAssignmentRead[]
  values: Record<number, WorkLogFormValue>
  onChangeField: (workAssignmentId: number, field: keyof WorkLogFormValue, value: string) => void
}

/** 業務記録入力欄（案件別の自由記述。数値実績は必須としない）。SC-06の仕事用実績入力
 * （仕様書6.5「仕事目標の実績入力」、要件定義書R-75）。ReadingLogFieldsと対になる。
 * 資格試験・読書と異なり日次ノルマ・残日数は持たないため、案件名のみ表示する。 */
export function WorkLogFields({ workAssignments, values, onChangeField }: WorkLogFieldsProps) {
  if (workAssignments.length === 0) {
    return null
  }

  return (
    <div className="flex flex-col gap-3">
      {workAssignments.map((workAssignment) => {
        const value = values[workAssignment.id]
        if (!value) {
          return null
        }
        return (
          <Card key={workAssignment.id}>
            <p className="font-medium text-gray-900">
              {workAssignment.client_name ?? t('dailyReport.workLog.noClientName')}
            </p>
            <label className="mt-2 flex flex-col gap-1 text-xs text-gray-600">
              {t('dailyReport.workLog.bodyLabel')}
              <Textarea
                rows={4}
                placeholder={t('dailyReport.workLog.bodyPlaceholder')}
                value={value.body}
                onChange={(e) => onChangeField(workAssignment.id, 'body', e.target.value)}
              />
            </label>
          </Card>
        )
      })}
    </div>
  )
}
