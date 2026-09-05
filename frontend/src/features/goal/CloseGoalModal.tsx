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
 *
 * 仕事目標（category=WORK）は資格試験・読書と異なり、受験結果登録の有無で自動判定
 * できないため、「結果あり（納品等）」「結果なし（中止・打ち切り）」を利用者が明示的に
 * 選択する（仕様書6.2「クローズ操作」、実装フェーズ分割計画書Phase23）。
 */
export function CloseGoalModal({
  goalId,
  category,
  open,
  onClose,
  onClosed,
}: {
  goalId: number
  category?: 'EXAM' | 'READING' | 'WORK'
  open: boolean
  onClose: () => void
  onClosed: () => void
}) {
  const { showApiError } = useToast()
  const [needsConfirmWithoutResult, setNeedsConfirmWithoutResult] = useState(false)

  const mutation = useMutation({
    mutationFn: (payload: { confirmWithoutResult?: boolean; withResult?: boolean }) =>
      closeGoal(goalId, {
        confirm_without_result: payload.confirmWithoutResult ?? false,
        with_result: payload.withResult ?? false,
      }),
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

  const handleClose = () => {
    setNeedsConfirmWithoutResult(false)
    onClose()
  }

  if (category === 'WORK') {
    return (
      <Modal open={open} onClose={handleClose} title={t('goals.detail.closeConfirm.title')}>
        <p className="text-sm text-gray-700">{t('goals.detail.closeConfirm.workBody')}</p>
        <div className="mt-4 flex justify-end gap-2">
          <Button variant="secondary" onClick={onClose}>
            {t('common.action.cancel')}
          </Button>
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
        </div>
      </Modal>
    )
  }

  return (
    <Modal open={open} onClose={handleClose} title={t('goals.detail.closeConfirm.title')}>
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
          onClick={() => mutation.mutate({ confirmWithoutResult: needsConfirmWithoutResult })}
        >
          {t('common.action.confirm')}
        </Button>
      </div>
    </Modal>
  )
}
