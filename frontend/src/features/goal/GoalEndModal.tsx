import { useMutation, useQueryClient } from '@tanstack/react-query'
import { t } from '../../locales/t'
import { Button } from '../../components/Button'
import { Modal } from '../../components/Modal'
import { useToast } from '../../components/Toast'
import { abandonGoal, completeGoal, type GoalCategory } from '../../api/goals'
import { QUERY_KEYS } from '../../constants/queryKeys'

/** 完了（実行中→完了）と中断（実行中・一時停止→中断）の別（開発Todo 1-3）。 */
export type GoalEndKind = 'complete' | 'abandon'

/**
 * 完了または中断の確認モーダル。確認は1回（開発Todo 1-11）。
 *
 * 文言は種別と操作の組でロケールに持つ（読書の完了は「読了」、仕事の中断は「中止・打ち切り」。
 * 開発Todo 1-2）。完了の可否（資格試験は全科目の合否登録が前提）は画面の完了ボタンで先に判定し、
 * ここでは確認だけを担う。
 */
export function GoalEndModal({
  goalId,
  category,
  kind,
  open,
  onClose,
  onDone,
}: {
  goalId: number
  category: GoalCategory
  kind: GoalEndKind
  open: boolean
  onClose: () => void
  onDone: () => void
}) {
  const queryClient = useQueryClient()
  const { showApiErrorWithTitle } = useToast()

  const mutation = useMutation({
    mutationFn: () => (kind === 'complete' ? completeGoal(goalId) : abandonGoal(goalId)),
    meta: { overlay: 'saving' },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.goal(goalId) })
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.goals() })
      onDone()
    },
    // 見出しは確認画面のタイトルと同じ（状態変更の失敗は操作名を見出しにする）。
    onError: (error) =>
      showApiErrorWithTitle(t(`goals.end.${kind}.${category}.title`), error),
  })

  return (
    <Modal open={open} onClose={onClose} title={t(`goals.end.${kind}.${category}.title`)}>
      <div className="flex flex-col gap-3 text-sm text-gray-700">
        <p>{t(`goals.end.${kind}.${category}.body`)}</p>
        <div className="mt-2 flex justify-end gap-2">
          <Button type="button" variant="secondary" onClick={onClose}>
            {t('common.action.cancel')}
          </Button>
          <Button type="button" disabled={mutation.isPending} onClick={() => mutation.mutate()}>
            {t(`goals.end.${kind}.confirmButton`)}
          </Button>
        </div>
      </div>
    </Modal>
  )
}
