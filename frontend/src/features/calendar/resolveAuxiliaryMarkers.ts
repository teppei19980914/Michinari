import type { components } from '../../types/api.d.ts'

type GoalDetailRead = components['schemas']['GoalDetailRead']

export type AuxiliaryMarker = 'EXAM_DATE' | 'EXAM_PERIOD' | 'LOAD_ADJUSTED'

/** 補助マーカー1件分（どの目標に由来するかを保持する。未決事項L-04関連）。
 * goal_id/goal_nameのsnake_case命名は、他画面のgoal_id付与レスポンス
 * （QuotaItemRead等）およびutils/groupByGoal.tsの前提と揃えるため。 */
export type AttributedAuxiliaryMarker = {
  marker: AuxiliaryMarker
  goal_id: number
  goal_name: string
}

const isWithin = (targetDate: string, from: string, to: string): boolean =>
  targetDate >= from && targetDate <= to

/**
 * カレンダーセルの補助表示（受験日・受験期間・負荷係数が1.0以外の期間）を判定する
 * （仕様書6.4 SC-05「補助表示」）。進行中の目標の科目・負荷プロファイルを横断して判定する
 * ため分岐が多く、目視確認では漏れやすい（技術選定書4.5と同じ理由でテスト対象とする）。
 *
 * 複数目標が同時進行している場合に、どの目標のマーカーかを区別できるよう
 * 目標ID・目標名を付与して返す（未決事項L-04）。同一目標内の重複（例: 複数科目が
 * 同日に試験日を持つ場合）のみ抑制し、目標をまたいだ重複排除は行わない
 * （元のSet実装は目標をまたいで種別だけで重複排除していたため、目標Aと目標Bが
 * 同じ種別のマーカーを同日に持つ場合に片方が消えてしまっていた）。
 */
export function resolveAuxiliaryMarkers(
  targetDate: string,
  activeGoals: GoalDetailRead[],
): AttributedAuxiliaryMarker[] {
  const markers: AttributedAuxiliaryMarker[] = []

  for (const goal of activeGoals) {
    const seenForGoal = new Set<AuxiliaryMarker>()
    const addMarker = (marker: AuxiliaryMarker) => {
      if (seenForGoal.has(marker)) {
        return
      }
      seenForGoal.add(marker)
      markers.push({ marker, goal_id: goal.id, goal_name: goal.name })
    }

    for (const subject of goal.exam_subjects) {
      if (subject.exam_date_type === 'FIXED' && subject.exam_date_fixed === targetDate) {
        addMarker('EXAM_DATE')
      }
      if (
        subject.exam_date_type === 'RANGE' &&
        subject.exam_date_from &&
        subject.exam_date_to &&
        isWithin(targetDate, subject.exam_date_from, subject.exam_date_to)
      ) {
        addMarker('EXAM_PERIOD')
      }
    }
    for (const profile of goal.load_profiles) {
      if (profile.coefficient !== 1 && isWithin(targetDate, profile.date_from, profile.date_to)) {
        addMarker('LOAD_ADJUSTED')
      }
    }
  }

  return markers
}
