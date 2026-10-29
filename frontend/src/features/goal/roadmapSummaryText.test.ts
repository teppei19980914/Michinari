import { describe, expect, it } from 'vitest'
import { buildRoadmapSummaryText } from './roadmapSummaryText'

describe('buildRoadmapSummaryText', () => {
  it('資格：遅れている場合', () => {
    expect(
      buildRoadmapSummaryText({
        category: 'EXAM',
        progressRatio: 0.62,
        overrunDays: 3,
        isAchieved: false,
      }),
    ).toBe('全体の62%、予定より3日遅れです')
  })

  it('資格：先行している場合', () => {
    expect(
      buildRoadmapSummaryText({
        category: 'EXAM',
        progressRatio: 0.5,
        overrunDays: -2,
        isAchieved: false,
      }),
    ).toBe('全体の50%、予定より2日先行しています')
  })

  it('資格：予定どおりの場合', () => {
    expect(
      buildRoadmapSummaryText({
        category: 'EXAM',
        progressRatio: 0.3,
        overrunDays: 0,
        isAchieved: false,
      }),
    ).toBe('全体の30%、予定どおり進んでいます')
  })

  it('資格：完了予測が無い場合（境界ケース：科目未登録）', () => {
    expect(
      buildRoadmapSummaryText({
        category: 'EXAM',
        progressRatio: 0,
        overrunDays: null,
        isAchieved: false,
      }),
    ).toBe('全体の0%です')
  })

  it('読書：遅れ/先行の判定は行わない（§0 U7）', () => {
    expect(
      buildRoadmapSummaryText({
        category: 'READING',
        progressRatio: 0.45,
        overrunDays: null,
        isAchieved: false,
      }),
    ).toBe('全体の45%まで読み進めました')
  })

  it('仕事：経過日数の割合を使う', () => {
    expect(
      buildRoadmapSummaryText({
        category: 'WORK',
        progressRatio: 0.8,
        overrunDays: null,
        isAchieved: false,
      }),
    ).toBe('評価期間の80%が経過しました')
  })

  it('境界値: 達成時はカテゴリに関わらず共通の文言になる', () => {
    expect(
      buildRoadmapSummaryText({
        category: 'READING',
        progressRatio: 1,
        overrunDays: null,
        isAchieved: true,
      }),
    ).toBe('目標を達成しました（100%）')
  })
})
