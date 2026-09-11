import { describe, expect, it } from 'vitest'
import { t } from '../../locales/t'
import { GOAL_CATEGORIES } from '../../constants/goalCategories'
import { resolveByGoalCategory } from './goalCategoryVariant'

/** 画面が目標種別ごとに出し分けているロケールキー（該当画面と同じ組を並べる）。 */
const CATEGORY_LABEL_KEYS = {
  /** BasicInfoTab: 基本情報タブの目標名ラベル。 */
  basicInfoNameLabel: {
    EXAM: 'goals.basicInfo.nameLabel',
    READING: 'goals.basicInfo.nameLabelReading',
    WORK: 'goals.basicInfo.nameLabelWork',
  },
  /** GoalsListPage: 新規作成モーダルの目標名ラベル。 */
  newGoalNameLabel: {
    EXAM: 'goals.new.nameLabel',
    READING: 'goals.new.nameLabelReading',
    WORK: 'goals.new.nameLabelWork',
  },
  /** GoalDetailPage: 基本情報タブのツールチップ（タブ定義が種別ごとに持つ）。 */
  basicInfoTooltip: {
    EXAM: 'goals.detail.tabTooltips.basicInfo',
    READING: 'goals.detail.tabTooltips.basicInfoReading',
    WORK: 'goals.detail.tabTooltips.basicInfoWork',
  },
} as const

describe('resolveByGoalCategory', () => {
  it('picks the variant for each category', () => {
    const variants = { EXAM: 'e', READING: 'r', WORK: 'w' }
    expect(resolveByGoalCategory('EXAM', variants)).toBe('e')
    expect(resolveByGoalCategory('READING', variants)).toBe('r')
    expect(resolveByGoalCategory('WORK', variants)).toBe('w')
  })

  it('works for non-string variants too', () => {
    const variants = { EXAM: { n: 1 }, READING: { n: 2 }, WORK: { n: 3 } }
    expect(resolveByGoalCategory('WORK', variants)).toEqual({ n: 3 })
  })

  it('covers every category so a new one cannot fall back silently', () => {
    // 入れ子三項の既定分岐で静かに資格試験へ落ちるのを防ぐのが本関数の目的。
    // 全種別が値を返す（undefinedにならない）ことを固定する。
    const variants = { EXAM: 'e', READING: 'r', WORK: 'w' }
    for (const category of GOAL_CATEGORIES) {
      expect(resolveByGoalCategory(category, variants)).toBeDefined()
    }
  })
})

describe('カテゴリ別ロケールキーの実在', () => {
  it('has a locale entry for every category of every category-specific label', () => {
    // t()は未登録キーをキー文字列のまま返すため、種別を追加したときの登録漏れは
    // 画面に生キーが出るまで気付けない。種別×ラベルの全組合せを横断的に固定する。
    for (const [name, keys] of Object.entries(CATEGORY_LABEL_KEYS)) {
      for (const category of GOAL_CATEGORIES) {
        const key = keys[category]
        expect(t(key), `${name} の未登録ロケールキー: ${key}`).not.toBe(key)
      }
    }
  })
})
