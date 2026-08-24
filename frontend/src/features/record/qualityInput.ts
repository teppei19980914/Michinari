import type { components } from '../../types/api.d.ts'

type QualityMetricType = components['schemas']['QualityMetricType']

export type QualityInputKind = 'HIDDEN' | 'PERCENT' | 'SUBJECTIVE_SCALE'

/**
 * 教材の品質指標方式から入力欄の形式を判定する（仕様書6.5「品質指標の入力形式」、
 * 技術選定書4.5「品質指標の入力形式切替: 3方式の分岐がある」）。
 *
 * - NONE: 入力欄自体を表示しない
 * - OBJECTIVE / SELF_SCORED: 0〜100の数値入力
 * - SUBJECTIVE: 5段階選択（内部的に20/40/60/80/100へ変換されるが、変換自体はサーバ側
 *   （record_service._normalize_quality）が担う。フロントは1〜5の選択値をそのまま送る）
 */
export function resolveQualityInputKind(qualityMetricType: QualityMetricType): QualityInputKind {
  if (qualityMetricType === 'NONE') {
    return 'HIDDEN'
  }
  if (qualityMetricType === 'SUBJECTIVE') {
    return 'SUBJECTIVE_SCALE'
  }
  return 'PERCENT'
}

export const SUBJECTIVE_SCALE_OPTIONS = [1, 2, 3, 4, 5] as const

/** 主観的手応え（1〜5）の入力値を検証する（サーバ側と同じ範囲、record_service._normalize_quality）。 */
export function isValidSubjectiveValue(value: number): boolean {
  return Number.isInteger(value) && value >= 1 && value <= 5
}

/** 客観正答率・自己採点得点率（0〜100）の入力値を検証する（仕様書10章）。 */
export function isValidPercentValue(value: number): boolean {
  return value >= 0 && value <= 100
}

/**
 * サーバに保存済みの正規化値（20/40/60/80/100）から、主観的手応え入力欄に再表示する
 * 1〜5の選択値を逆算する（ロジック・プロンプト編14.1の変換表 {1:20,2:40,3:60,4:80,5:100} の逆写像）。
 * 進捗のみ登録済の記録を日次報告へ昇格する際、既存値を選択欄へ復元するために使う。
 */
export function subjectiveScaleFromNormalized(normalized: number): number | null {
  const scale = normalized / 20
  return isValidSubjectiveValue(scale) ? scale : null
}
