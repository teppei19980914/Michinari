/** 単語帳の習得の可視化（開発Todo_単語帳_v1.0 要件E E-U8）の設定の入力判定のテスト。 */
import { describe, expect, it } from 'vitest'
import {
  buildVocabMasterySettingsPayload,
  resolveVocabMasterySettingsGuard,
  type VocabMasterySettingsDraft,
} from './vocabMasterySettings'

const VALID_DRAFT: VocabMasterySettingsDraft = {
  masteryStreak: 3,
  masteredTermsThresholds: '10,30,50',
}

describe('resolveVocabMasterySettingsGuard', () => {
  it('allows saving when both fields are valid', () => {
    expect(resolveVocabMasterySettingsGuard(VALID_DRAFT)).toEqual({
      canSubmit: true,
      errorKey: null,
    })
  })

  it.each([0, -1, 1.5])('blocks saving when masteryStreak is %s', (masteryStreak) => {
    expect(resolveVocabMasterySettingsGuard({ ...VALID_DRAFT, masteryStreak })).toEqual({
      canSubmit: false,
      errorKey: 'settings.vocabMastery.masteryStreakInvalid',
    })
  })

  it('blocks saving when masteredTermsThresholds is malformed', () => {
    expect(
      resolveVocabMasterySettingsGuard({ ...VALID_DRAFT, masteredTermsThresholds: '10,abc' }),
    ).toEqual({
      canSubmit: false,
      errorKey: 'settings.vocabMastery.thresholdsInvalid',
    })
  })
})

describe('buildVocabMasterySettingsPayload', () => {
  it('maps fields to their snake_case API keys', () => {
    expect(buildVocabMasterySettingsPayload(VALID_DRAFT)).toEqual({
      mastery_streak: 3,
      mastered_terms_thresholds: '10,30,50',
    })
  })
})
