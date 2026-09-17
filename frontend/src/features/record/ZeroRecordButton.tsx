import { useState } from 'react'
import { t } from '../../locales/t'
import { Button } from '../../components/Button'
import { Modal } from '../../components/Modal'
import { useDayType } from './useDayType'
import { useZeroRecordAction } from './useZeroRecordAction'
import { resolveZeroRecordMessage } from './zeroRecordMessage'
import type { CategoryPresence } from './categoryCompletion'
import type { ZeroRecordCategory } from './resolveZeroRecordCategories'

export type ZeroRecordButtonProps = {
  targetDate: string
  /** ゼロ確定の対象カテゴリ（resolveZeroRecordCategories）。空なら何も表示しない。 */
  categories: ZeroRecordCategory[]
  presence: CategoryPresence
}

/**
 * 「今日は何もしていない」ボタン（仕様書6.5改、記録画面改善タスク2026-09-17）。
 *
 * 対象カテゴリが無ければ表示しない（既に全て報告済み・進捗のみ登録済み、または着手中の
 * 目標が無い日）。誤操作防止のため確定前に確認モーダルを挟む（CloseGoalModal.tsxと同じ
 * 方針。確定は取り消せないため）。
 */
export function ZeroRecordButton({ targetDate, categories, presence }: ZeroRecordButtonProps) {
  const [open, setOpen] = useState(false)
  const dayTypeQuery = useDayType(targetDate)
  const message = resolveZeroRecordMessage(dayTypeQuery.data ?? 'PLAN')
  const action = useZeroRecordAction({ targetDate, categories, presence, message })

  if (categories.length === 0) {
    return null
  }

  return (
    <>
      <div className="flex justify-end">
        <Button variant="secondary" onClick={() => setOpen(true)}>
          {t('dailyReport.zeroRecord.button')}
        </Button>
      </div>
      <Modal
        open={open}
        onClose={() => setOpen(false)}
        title={t('dailyReport.zeroRecord.confirmTitle')}
      >
        <p className="text-sm text-gray-700">{t('dailyReport.zeroRecord.confirmBody')}</p>
        <div className="mt-4 flex justify-end gap-2">
          <Button variant="secondary" onClick={() => setOpen(false)}>
            {t('dailyReport.zeroRecord.confirmCancel')}
          </Button>
          <Button
            disabled={action.isPending}
            onClick={() => {
              setOpen(false)
              action.submit()
            }}
          >
            {t('dailyReport.zeroRecord.confirmSubmit')}
          </Button>
        </div>
      </Modal>
    </>
  )
}
