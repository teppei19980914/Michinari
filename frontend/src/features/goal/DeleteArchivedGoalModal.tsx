import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { t } from '../../locales/t'
import { Button } from '../../components/Button'
import { Modal } from '../../components/Modal'
import { useToast } from '../../components/Toast'
import { deleteArchivedGoal, type GoalRead } from '../../api/goals'
import { resolveDeleteGoalLabelKeys } from './deleteGoalLabels'

/**
 * MD-08 完全削除確認（仕様書5.3・6.15）。学習実績も含めるかのチェックボックスを持つ。
 *
 * 取り消せない操作のため、何が削除されるのかを目標種別ごとの文言で正しく伝える
 * （道連れ対象は資格試験=教材・学習実績、読書=書籍・想起記録、仕事=案件情報・業務記録。
 * データ構造編4.2）。文言の選択は`resolveDeleteGoalLabelKeys`が担う。
 *
 * GoalsListPage内の内部関数から切り出したのは、描画テストを書けるようにするため
 * （CloseGoalModalと同じ置き方に揃えた）。
 */
export function DeleteArchivedGoalModal({
  goal,
  onClose,
}: {
  goal: GoalRead | null
  onClose: () => void
}) {
  const queryClient = useQueryClient()
  const { showApiError } = useToast()
  const [cascadeStudyLogs, setCascadeStudyLogs] = useState(true)

  const mutation = useMutation({
    mutationFn: (goalId: number) =>
      deleteArchivedGoal(goalId, { cascade_study_logs: cascadeStudyLogs }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['goals'] })
      onClose()
    },
    onError: showApiError,
  })

  // 文言は目標種別ごとに異なる（何が消えるのかを正しく伝えるため）。goalが無い間は
  // 種別を決められないため、既定の種別で代用せずモーダルごと描画しない。
  if (goal === null) {
    return null
  }
  const labelKeys = resolveDeleteGoalLabelKeys(goal.category)

  return (
    <Modal open onClose={onClose} title={t('goals.list.deleteModal.title')}>
      <div className="flex flex-col gap-3 text-sm text-gray-700">
        <p>{t(labelKeys.warningKey)}</p>
        <label className="flex items-start gap-2">
          <input
            type="checkbox"
            className="mt-1"
            checked={cascadeStudyLogs}
            onChange={(e) => setCascadeStudyLogs(e.target.checked)}
          />
          <span>
            {t(labelKeys.cascadeCheckboxKey)}
            <span className="mt-0.5 block text-xs text-gray-500">
              {t(labelKeys.cascadeHintKey)}
            </span>
          </span>
        </label>
        <div className="mt-2 flex justify-end gap-2">
          <Button type="button" variant="secondary" onClick={onClose}>
            {t('common.action.cancel')}
          </Button>
          <Button
            type="button"
            disabled={mutation.isPending}
            onClick={() => mutation.mutate(goal.id)}
          >
            {t('goals.list.deleteModal.confirmButton')}
          </Button>
        </div>
      </div>
    </Modal>
  )
}
