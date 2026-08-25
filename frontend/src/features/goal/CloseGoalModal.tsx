import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { t } from '../../locales/t'
import { Button } from '../../components/Button'
import { Modal } from '../../components/Modal'
import { useToast } from '../../components/Toast'
import { ApiError } from '../../api/client'
import { closeGoal } from '../../api/goals'

/**
 * 目標のクローズ確認モーダル（仕様書7.1・6.9 MD-03）。GoalDetailPage（SC-03、クローズ後は
 * その場に留まる）とExamResultPage（SC-10、クローズ後はSC-13へ遷移し総括レポート生成を
 * 開始する）の両方から使う。差分は`onClosed`コールバックのみに閉じ込める
 * （CLAUDE.md DRYの原則、dry-reviewer指摘対応）。
 */
export function CloseGoalModal({
  goalId,
  open,
  onClose,
  onClosed,
}: {
  goalId: number
  open: boolean
  onClose: () => void
  onClosed: () => void
}) {
  const { showApiError } = useToast()
  const [needsConfirmWithoutResult, setNeedsConfirmWithoutResult] = useState(false)

  const mutation = useMutation({
    mutationFn: (confirmWithoutResult: boolean) =>
      closeGoal(goalId, { confirm_without_result: confirmWithoutResult }),
    onSuccess: () => {
      setNeedsConfirmWithoutResult(false)
      onClosed()
    },
    onError: (error) => {
      if (error instanceof ApiError && error.code === 'INVALID_STATE_TRANSITION') {
        setNeedsConfirmWithoutResult(true)
        return
      }
      showApiError(error)
    },
  })

  return (
    <Modal
      open={open}
      onClose={() => {
        setNeedsConfirmWithoutResult(false)
        onClose()
      }}
      title={t('goals.detail.closeConfirm.title')}
    >
      <p className="text-sm text-gray-700">
        {needsConfirmWithoutResult
          ? t('goals.detail.closeConfirm.withoutResultBody')
          : t('goals.detail.closeConfirm.body')}
      </p>
      <div className="mt-4 flex justify-end gap-2">
        <Button variant="secondary" onClick={onClose}>
          {t('common.action.cancel')}
        </Button>
        <Button
          disabled={mutation.isPending}
          onClick={() => mutation.mutate(needsConfirmWithoutResult)}
        >
          {t('common.action.confirm')}
        </Button>
      </div>
    </Modal>
  )
}
