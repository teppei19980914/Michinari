import type { GoalRead } from '../../api/goals'
import type { components } from '../../types/api.d.ts'

type DiaryEntryRead = components['schemas']['DiaryEntryRead']

export type DiaryEntryWithGoalId = DiaryEntryRead & { goal_id: number }

/** 単語帳への用語提案（開発Todo_単語帳_v1.0 要件D）の対象となる日記エントリを選ぶ。
 *
 * 対象はEXAM目標の、日記（学んだこと）が書かれているものだけ。バックエンドの
 * `daily_goal_diary`は現状EXAM確定フロー（`record_service_exam`）のみが書き込むため、
 * 実際にはEXAM以外の目標の日記エントリが混ざることは無いが、表示・API呼び出しの両方で
 * 無駄な処理を避けるため、呼び出し側が持つEXAM目標ID集合への絞り込みをここでも行う
 * （dry-reviewer・performance-reviewerレビューで検出、2026-11-21。`ExamReportSection.tsx`・
 * `DailyReportViewPage.tsx`・`useDailyReportActions.ts`の3箇所で同じ判定が重複していた）。
 */
export function selectDiaryEntriesEligibleForVocabSuggestions(
  diaryEntries: DiaryEntryRead[],
  examGoalIds: ReadonlySet<number>,
): DiaryEntryWithGoalId[] {
  return diaryEntries.filter(
    (entry): entry is DiaryEntryWithGoalId =>
      entry.goal_id !== null &&
      examGoalIds.has(entry.goal_id) &&
      Boolean(entry.diary_learned?.trim()),
  )
}

/** 日次報告閲覧（DailyReportViewPage）で、提案カード・手動追加ボタンの対象とするEXAM目標IDを
 * 決める。目標タブで選択中ならそれ（EXAMのときのみ）、無ければ日記のある目標、無ければ
 * `examGoalIds`（呼び出し側がACTIVEなEXAM目標IDの集合を渡す）の先頭。対象が無ければnull。
 */
export function resolveExamGoalIdForVocab({
  selectedGoal,
  diaryEntries,
  examGoalIds,
}: {
  selectedGoal: Pick<GoalRead, 'id' | 'category'> | undefined
  diaryEntries: DiaryEntryRead[]
  examGoalIds: ReadonlySet<number>
}): number | null {
  if (selectedGoal?.category === 'EXAM') {
    return selectedGoal.id
  }
  const [firstEligible] = selectDiaryEntriesEligibleForVocabSuggestions(diaryEntries, examGoalIds)
  if (firstEligible) {
    return firstEligible.goal_id
  }
  const [firstExamGoalId] = examGoalIds
  return firstExamGoalId ?? null
}
