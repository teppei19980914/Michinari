import { describe, expect, it } from 'vitest'
import { t } from '../../locales/t'
import { GOAL_CATEGORIES } from '../../constants/goalCategories'
import { resolveDeleteGoalLabelKeys } from './deleteGoalLabels'

describe('resolveDeleteGoalLabelKeys', () => {
  it('uses the exam wording (no suffix) for an exam goal', () => {
    expect(resolveDeleteGoalLabelKeys('EXAM')).toEqual({
      warningKey: 'goals.list.deleteModal.warning',
      cascadeCheckboxKey: 'goals.list.deleteModal.cascadeCheckbox',
      cascadeHintKey: 'goals.list.deleteModal.cascadeHint',
    })
  })

  it('uses the book wording for a reading goal', () => {
    // 読書目標の道連れ対象は書籍・想起記録であり「科目・教材」ではない（データ構造編4.2）。
    expect(resolveDeleteGoalLabelKeys('READING')).toEqual({
      warningKey: 'goals.list.deleteModal.warningReading',
      cascadeCheckboxKey: 'goals.list.deleteModal.cascadeCheckboxReading',
      cascadeHintKey: 'goals.list.deleteModal.cascadeHintReading',
    })
  })

  it('uses the assignment wording for a work goal', () => {
    expect(resolveDeleteGoalLabelKeys('WORK')).toEqual({
      warningKey: 'goals.list.deleteModal.warningWork',
      cascadeCheckboxKey: 'goals.list.deleteModal.cascadeCheckboxWork',
      cascadeHintKey: 'goals.list.deleteModal.cascadeHintWork',
    })
  })

  it('resolves every key to an actual locale entry', () => {
    // t()は未登録キーをキー文字列のまま返すため、キー名の誤りは画面に生キーが出るまで
    // 気付けない。全種別×全キーが実在することをここで固定する。
    for (const category of GOAL_CATEGORIES) {
      for (const key of Object.values(resolveDeleteGoalLabelKeys(category))) {
        expect(t(key), `未登録のロケールキー: ${key}`).not.toBe(key)
      }
    }
  })
})
