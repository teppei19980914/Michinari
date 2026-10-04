import { describe, expect, it } from 'vitest'
import { t } from '../../locales/t'
import { GOAL_CATEGORIES } from '../../constants/goalCategories'
import { resolveDeleteGoalWarningKey } from './deleteGoalLabels'

describe('resolveDeleteGoalWarningKey', () => {
  it('uses the exam wording for an exam goal', () => {
    expect(resolveDeleteGoalWarningKey('EXAM')).toBe('goals.delete.warning.EXAM')
  })

  it('uses the book wording for a reading goal', () => {
    // 読書目標の道連れ対象は書籍・想起記録であり「教材・学習実績」ではない（データ構造編4.2）。
    expect(resolveDeleteGoalWarningKey('READING')).toBe('goals.delete.warning.READING')
  })

  it('uses the assignment wording for a work goal', () => {
    expect(resolveDeleteGoalWarningKey('WORK')).toBe('goals.delete.warning.WORK')
  })

  it('resolves every category to an actual locale entry', () => {
    // t()は未登録キーをキー文字列のまま返すため、キー名の誤りは画面に生キーが出るまで
    // 気付けない。全種別のキーが実在することをここで固定する。
    for (const category of GOAL_CATEGORIES) {
      const key = resolveDeleteGoalWarningKey(category)
      expect(t(key), `未登録のロケールキー: ${key}`).not.toBe(key)
    }
  })
})
