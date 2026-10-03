import type { DiaryEntryInput, DiaryEntryRead } from '../../api/records'
import type { GoalRead } from '../../api/goals'

/**
 * 日記入力欄の1目標分の入力状態。
 *
 * 入力欄は「学んだこと・理解したこと」1つに集約した（利用者が入力先に迷わないため。
 * 振り返りセクションでテーマ別にまとめる対象もこの欄）。diaryBodyは旧仕様（質問への回答と
 * 「自由に書く」欄）で保存された本文で、入力欄としては編集させず、保存時にそのまま
 * 引き継ぐ（既存の記録を失わないため）。
 */
export type DiaryFormValue = {
  diaryLearned: string
  diaryBody: string
}

const EMPTY_VALUE: DiaryFormValue = { diaryLearned: '', diaryBody: '' }

/**
 * 日記入力欄の初期値を組み立てる（studyLogForm.initStudyLogFormValuesと同じマージ
 * パターン）。対象は現在ACTIVEな全目標とする。
 */
export function initDiaryFormValues(
  activeGoals: GoalRead[],
  existingEntries: DiaryEntryRead[],
): Record<number, DiaryFormValue> {
  const existingByGoal = new Map(
    existingEntries
      .filter((entry): entry is DiaryEntryRead & { goal_id: number } => entry.goal_id !== null)
      .map((entry) => [entry.goal_id, entry]),
  )
  const result: Record<number, DiaryFormValue> = {}
  for (const goal of activeGoals) {
    const existing = existingByGoal.get(goal.id)
    result[goal.id] = existing
      ? {
          diaryLearned: existing.diary_learned ?? '',
          diaryBody: existing.diary_body ?? '',
        }
      : { ...EMPTY_VALUE }
  }
  return result
}

/** 入力欄に何かしら値が入っているか（離脱確認・確定可否の判定に使う）。引き継ぎの本文は含めない。 */
export function hasAnyDiaryInput(values: Record<number, DiaryFormValue>): boolean {
  return Object.values(values).some((value) => value.diaryLearned.trim() !== '')
}

/**
 * 送信用ペイロードを組み立てる。本文・学んだこと両方が空の目標は送信対象から除外する
 * （buildStudyLogPayloadと同じ考え方）。
 */
export function buildDiaryEntriesPayload(
  values: Record<number, DiaryFormValue>,
): DiaryEntryInput[] {
  return Object.entries(values)
    .map(([goalId, value]) => ({
      goal_id: Number(goalId),
      diary_body: value.diaryBody,
      diary_learned: value.diaryLearned,
    }))
    .filter((entry) => entry.diary_body !== '' || entry.diary_learned.trim() !== '')
}

/**
 * 実際に記述のある日記だけを取り出す（確定済みサマリの表示用）。
 *
 * 日記は目標ごとに枠が作られるため、何も書かずに確定した目標の分は本文・学びともに空で
 * 保存される。空の枠をそのまま並べると見出しだけが並ぶため除く。日次報告（SC-06）と
 * 日次報告閲覧（SC-08）で同じ判定が要るため共通化する（CODING_RULES.md「①DRYの原則」）。
 */
export function filterWrittenDiaryEntries(entries: DiaryEntryRead[]): DiaryEntryRead[] {
  return entries.filter((entry) => entry.diary_body || entry.diary_learned)
}
