import type { components } from '../../types/api.d.ts'

type GoalDetailRead = components['schemas']['GoalDetailRead']

export type AuxiliaryMarker = 'EXAM_DATE' | 'EXAM_PERIOD' | 'LOAD_ADJUSTED'

const isWithin = (targetDate: string, from: string, to: string): boolean =>
  targetDate >= from && targetDate <= to

/**
 * カレンダーセルの補助表示（受験日・受験期間・負荷係数が1.0以外の期間）を判定する
 * （仕様書6.4 SC-05「補助表示」）。進行中の目標の科目・負荷プロファイルを横断して判定する
 * ため分岐が多く、目視確認では漏れやすい（技術選定書4.5と同じ理由でテスト対象とする）。
 */
export function resolveAuxiliaryMarkers(
  targetDate: string,
  activeGoals: GoalDetailRead[],
): AuxiliaryMarker[] {
  const markers = new Set<AuxiliaryMarker>()

  for (const goal of activeGoals) {
    for (const subject of goal.exam_subjects) {
      if (subject.exam_date_type === 'FIXED' && subject.exam_date_fixed === targetDate) {
        markers.add('EXAM_DATE')
      }
      if (
        subject.exam_date_type === 'RANGE' &&
        subject.exam_date_from &&
        subject.exam_date_to &&
        isWithin(targetDate, subject.exam_date_from, subject.exam_date_to)
      ) {
        markers.add('EXAM_PERIOD')
      }
    }
    for (const profile of goal.load_profiles) {
      if (profile.coefficient !== 1 && isWithin(targetDate, profile.date_from, profile.date_to)) {
        markers.add('LOAD_ADJUSTED')
      }
    }
  }

  return [...markers]
}
