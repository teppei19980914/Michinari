/**
 * 単語帳の習得の可視化（開発Todo_単語帳_v1.0 要件E E-U1・E-U2・E-U8）の設定の入力判定。
 *
 * 閾値（`mastered_terms_thresholds`）の検証は、節目の閾値設定（milestoneThresholdSettings.ts）
 * と同じ形式（カンマ区切りの正の整数）であり、`isValidThresholdList`を再利用する
 * （CODING_RULES.md「DRYの原則」）。
 */
import type { AppSettingsUpdate } from '../../api/settings'
import { isValidThresholdList } from './milestoneThresholdSettings'

export type VocabMasterySettingsDraft = {
  masteryStreak: number
  masteredTermsThresholds: string
}

export type VocabMasterySettingsGuard = {
  canSubmit: boolean
  errorKey: string | null
}

export function resolveVocabMasterySettingsGuard(
  draft: VocabMasterySettingsDraft,
): VocabMasterySettingsGuard {
  if (!Number.isInteger(draft.masteryStreak) || draft.masteryStreak < 1) {
    return { canSubmit: false, errorKey: 'settings.vocabMastery.masteryStreakInvalid' }
  }
  if (!isValidThresholdList(draft.masteredTermsThresholds)) {
    return { canSubmit: false, errorKey: 'settings.vocabMastery.thresholdsInvalid' }
  }
  return { canSubmit: true, errorKey: null }
}

export function buildVocabMasterySettingsPayload(
  draft: VocabMasterySettingsDraft,
): NonNullable<AppSettingsUpdate['vocab_mastery']> {
  return {
    mastery_streak: draft.masteryStreak,
    mastered_terms_thresholds: draft.masteredTermsThresholds,
  }
}
