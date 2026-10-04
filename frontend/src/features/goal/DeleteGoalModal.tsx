import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { t } from '../../locales/t'
import { Button } from '../../components/Button'
import { Input } from '../../components/Input'
import { Modal } from '../../components/Modal'
import { useToast } from '../../components/Toast'
import { deleteGoal, type GoalRead } from '../../api/goals'
import { QUERY_KEYS } from '../../constants/queryKeys'
import { resolveDeleteGoalWarningKey } from './deleteGoalLabels'

/**
 * 目標の削除（開発Todo 1-4）。実行中以外のすべての状態（アーカイブ済みを含む）が対象で、
 * 関連データはすべて削除される。取り消せないため二段階で確認する：警告を読み、目標名を入力して確定する。
 */
export function DeleteGoalModal({ goal, onClose }: { goal: GoalRead | null; onClose: () => void }) {
  if (goal === null) {
    return null
  }
  // 目標が変わるたびに入力欄を空に戻すため、目標ごとに別インスタンスとして描画する。
  return <DeleteGoalDialog key={goal.id} goal={goal} onClose={onClose} />
}

function DeleteGoalDialog({ goal, onClose }: { goal: GoalRead; onClose: () => void }) {
  const queryClient = useQueryClient()
  const { showApiErrorWithTitle } = useToast()
  const [typedName, setTypedName] = useState('')

  const mutation = useMutation({
    mutationFn: () => deleteGoal(goal.id),
    meta: { overlay: 'deleting' },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.goals() })
      onClose()
    },
    onError: (error) => showApiErrorWithTitle(t('goals.delete.title'), error),
  })

  const confirmed = typedName === goal.name

  return (
    <Modal open onClose={onClose} title={t('goals.delete.title')}>
      <div className="flex flex-col gap-3 text-sm text-gray-700">
        <p>{t(resolveDeleteGoalWarningKey(goal.category))}</p>
        <label className="flex flex-col gap-1">
          {t('goals.delete.typeNamePrompt', { name: goal.name })}
          <Input value={typedName} onChange={(e) => setTypedName(e.target.value)} />
        </label>
        <div className="mt-2 flex justify-end gap-2">
          <Button type="button" variant="secondary" onClick={onClose}>
            {t('common.action.cancel')}
          </Button>
          <Button
            type="button"
            disabled={!confirmed || mutation.isPending}
            onClick={() => mutation.mutate()}
          >
            {t('goals.delete.confirmButton')}
          </Button>
        </div>
      </div>
    </Modal>
  )
}
