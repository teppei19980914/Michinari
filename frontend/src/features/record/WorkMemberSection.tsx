import { t } from '../../locales/t'
import type { ActiveWorkAssignment } from '../../api/goals'
import { WorkMemberList } from '../goal/WorkMemberList'

/** 日次報告画面でのチームメンバー編集（要件定義書6.11「同期」）。
 *
 * 目標詳細画面（WorkAssignmentTab）と同じWorkMemberListコンポーネント・同じAPI・
 * 同じクエリキーを使うことで、追加の同期機構なしに双方の画面で常に同じデータを表示する。
 * アクティブな仕事目標は複数同時進行しうるため（読書・資格試験と異なる）、案件ごとに
 * 1ブロックずつ表示する。
 */
export function WorkMemberSection({
  workAssignments,
}: {
  workAssignments: ActiveWorkAssignment[]
}) {
  /* v8 ignore next 3 -- 呼び出し元（DailyReportPage）はtargets.showWorkSection
     （workAssignments.length > 0が前提）のときのみこのコンポーネントを描画するため
     到達しない防御的分岐（OPERATIONS.md「到達不能な防御的分岐」）。 */
  if (workAssignments.length === 0) {
    return null
  }

  return (
    <div className="flex flex-col gap-3">
      {workAssignments.map(({ goal, workAssignment }) => (
        <div key={workAssignment.id} className="flex flex-col gap-2">
          <h2 className="text-sm font-semibold text-gray-900">
            {t('dailyReport.workMember.title', { workName: goal.name })}
          </h2>
          <WorkMemberList goalId={goal.id} members={workAssignment.members} readOnly={false} />
        </div>
      ))}
    </div>
  )
}
