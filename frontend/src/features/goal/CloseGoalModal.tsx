import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { t } from '../../locales/t'
import { Button } from '../../components/Button'
import { Modal } from '../../components/Modal'
import { useToast } from '../../components/Toast'
import { closeGoal, type GoalCategory } from '../../api/goals'
import {
  isCloseConfirmationRequired,
  resolveCloseGoalConfirmView,
  toCloseGoalRequest,
} from './closeGoalConfirm'

/**
 * 目標のクローズ確認モーダル（仕様書7.1・6.9 MD-03）。GoalDetailPage（SC-03、クローズ後は
 * その場に留まる）とExamResultPage（SC-10、クローズ後はSC-13へ遷移し総括レポート生成を
 * 開始する）の両方から使う。差分は`onClosed`コールバックのみに閉じ込める
 * （CLAUDE.md DRYの原則、dry-reviewer指摘対応）。
 *
 * 種別ごとの表示・送信値の判定と、失敗が確認待ちかどうかの判定は`closeGoalConfirm.ts`の
 * 純粋関数（単体テストあり）が担い、本コンポーネントは描画と通信に専念する。
 */
export function CloseGoalModal({
  goalId,
  category,
  open,
  onClose,
  onClosed,
}: {
  goalId: number
  /** 必須。省略を許すと渡し忘れが静かに資格試験として扱われるため。 */
  category: GoalCategory
  open: boolean
  onClose: () => void
  onClosed: () => void
}) {
  const { showApiError } = useToast()
  const [awaitingConfirmWithoutResult, setAwaitingConfirmWithoutResult] = useState(false)
  const closeConfirmView = resolveCloseGoalConfirmView({ category, awaitingConfirmWithoutResult })

  const mutation = useMutation({
    mutationFn: (payload: { confirmWithoutResult?: boolean; withResult?: boolean }) =>
      closeGoal(goalId, toCloseGoalRequest(payload)),
    onSuccess: () => {
      setAwaitingConfirmWithoutResult(false)
      onClosed()
    },
    onError: (error) => {
      if (isCloseConfirmationRequired(error)) {
        setAwaitingConfirmWithoutResult(true)
        return
      }
      showApiError(error)
    },
  })

  // 閉じる経路は必ずここへ集約する。確認待ちのまま閉じると、次に開いたときに確認済みの
  // 状態から始まり「確定」1回で結果なしクローズが確定してしまう。
  const handleClose = () => {
    setAwaitingConfirmWithoutResult(false)
    onClose()
  }

  return (
    <Modal open={open} onClose={handleClose} title={t('goals.detail.closeConfirm.title')}>
      <p className="text-sm text-gray-700">{t(closeConfirmView.bodyKey)}</p>
      <div className="mt-4 flex justify-end gap-2">
        <Button variant="secondary" onClick={handleClose}>
          {t('common.action.cancel')}
        </Button>
        {closeConfirmView.mode === 'RESULT_CHOICE' ? (
          <>
            <Button
              variant="secondary"
              disabled={mutation.isPending}
              onClick={() => mutation.mutate({ withResult: false })}
            >
              {t('goals.detail.closeConfirm.workWithoutResult')}
            </Button>
            <Button
              disabled={mutation.isPending}
              onClick={() => mutation.mutate({ withResult: true })}
            >
              {t('goals.detail.closeConfirm.workWithResult')}
            </Button>
          </>
        ) : (
          <Button
            disabled={mutation.isPending}
            onClick={() =>
              mutation.mutate({ confirmWithoutResult: closeConfirmView.confirmWithoutResult })
            }
          >
            {t('common.action.confirm')}
          </Button>
        )}
      </div>
    </Modal>
  )
}
