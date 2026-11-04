import { MilestoneCelebrationModal } from '../milestone/MilestoneCelebrationModal'
import type { MilestoneCelebrationForPage } from './useDailyReportActions'
import { ZeroRecordButton } from './ZeroRecordButton'
import type { ZeroRecordCategory } from './resolveZeroRecordCategories'
import type { CategoryPresence } from './categoryCompletion'
import type { GoalCategory } from '../../api/goals'

type RecordConfirmationExtrasProps = {
  targetDate: string
  zeroRecordCategories: ZeroRecordCategory[]
  presence: CategoryPresence
  goalIdsByCategory: Record<GoalCategory, number | null>
  milestoneCelebration: MilestoneCelebrationForPage
}

/** 「何もしていない」ボタンと節目のお祝いモーダルをまとめる（DailyReportPageの行数を
 * 抑えるための束ね、CODING_RULES.md 保守性: max-lines-per-function）。両者とも確定後に
 * 発生しうる出来事（ゼロ確定・節目到達）を扱う点で役割が近い。 */
export function RecordConfirmationExtras({
  targetDate,
  zeroRecordCategories,
  presence,
  goalIdsByCategory,
  milestoneCelebration,
}: RecordConfirmationExtrasProps) {
  return (
    <>
      <ZeroRecordButton
        targetDate={targetDate}
        categories={zeroRecordCategories}
        presence={presence}
        goalIdsByCategory={goalIdsByCategory}
        checkMilestones={milestoneCelebration.checkGoal}
      />
      <MilestoneCelebrationModal
        milestone={milestoneCelebration.current}
        onClose={milestoneCelebration.onDismiss}
      />
    </>
  )
}
