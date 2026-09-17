import { t } from '../../locales/t'
import type { DiaryEntryInput, DiaryEntryRead } from '../../api/records'
import type { GoalRead } from '../../api/goals'
import { combineQaAnswers, hasAnyQaInput } from './qaCombine'

/**
 * 日記入力欄の1目標分の入力状態。
 *
 * 「本日の行動・所感」は質問への回答形式へ再構成した（仕様書6.5改、記録画面改善タスク
 * 2026-09-17）。questionAnswersが質問ごとの回答、freeTextが「自由に書く」欄（旧・本日の
 * 行動・所感欄）に対応する。送信する日記本文（diary_body）はこの2つをcombineDiaryBodyで
 * 都度結合して求め、保存形式・APIは変更しない。
 */
export type DiaryFormValue = {
  diaryLearned: string
  questionAnswers: string[]
  freeText: string
}

/** 資格試験の日記質問（仕様書6.5改）。固定2問。 */
export function getDiaryQuestions(): string[] {
  return [t('dailyReport.diary.question1'), t('dailyReport.diary.question2')]
}

const EMPTY_VALUE: DiaryFormValue = {
  diaryLearned: '',
  questionAnswers: ['', ''],
  freeText: '',
}

/**
 * 質問への回答と「自由に書く」欄を結合し、送信する日記本文（diary_body）を求める。
 *
 * @example
 * combineDiaryBody({ diaryLearned: '', questionAnswers: ['', ''], freeText: '今日は頑張った' })
 * // => '今日は頑張った'
 */
export function combineDiaryBody(value: DiaryFormValue): string {
  return combineQaAnswers(getDiaryQuestions(), value.questionAnswers, value.freeText)
}

/**
 * 日記入力欄の初期値を組み立てる（studyLogForm.initStudyLogFormValuesと同じマージ
 * パターン）。対象は現在ACTIVEな全目標とし、先行着手した内容を自由記述できる現行の
 * 逃げ道（仕様書6.5）を維持する。
 *
 * 既存の日記本文（サーバ保存済み）は「自由に書く」欄（freeText）へそのまま引き継ぐ
 * （質問への回答へ逆変換はしない。質問形式の導入前に書かれた本文、および進捗のみ登録から
 * 継続して報告する場合のいずれも、既存の文章を失わず・ラベルを付け足さずに引き継ぐため）。
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
          questionAnswers: ['', ''],
          freeText: existing.diary_body ?? '',
        }
      : { ...EMPTY_VALUE, questionAnswers: [...EMPTY_VALUE.questionAnswers] }
  }
  return result
}

/** 入力欄に何かしら値が入っているか（離脱確認・確定可否の判定に使う）。 */
export function hasAnyDiaryInput(values: Record<number, DiaryFormValue>): boolean {
  return Object.values(values).some(
    (value) =>
      value.diaryLearned.trim() !== '' || hasAnyQaInput(value.questionAnswers, value.freeText),
  )
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
      diary_body: combineDiaryBody(value),
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
