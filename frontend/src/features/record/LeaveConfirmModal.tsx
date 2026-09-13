import type { Blocker } from 'react-router-dom'
import { t } from '../../locales/t'
import { Modal } from '../../components/Modal'
import { Button } from '../../components/Button'

/** 確定前に画面を離れようとしたときの確認ダイアログ（仕様書6.5）。
 *
 * ブロック中（state === 'blocked'）のBlockerだけがreset/proceedを持つため、先に絞り込んでから
 * 描画する。ブロックしていない間はダイアログ自体を出さないので、早期returnで問題ない。 */
export function LeaveConfirmModal({ blocker }: { blocker: Blocker }) {
  if (blocker.state !== 'blocked') {
    return null
  }

  return (
    <Modal open onClose={blocker.reset} title={t('dailyReport.leaveConfirm.title')}>
      <p className="text-sm text-gray-700">{t('dailyReport.leaveConfirm.body')}</p>
      <div className="mt-4 flex justify-end gap-2">
        <Button variant="secondary" onClick={blocker.reset}>
          {t('dailyReport.leaveConfirm.stay')}
        </Button>
        <Button onClick={blocker.proceed}>{t('dailyReport.leaveConfirm.leave')}</Button>
      </div>
    </Modal>
  )
}
