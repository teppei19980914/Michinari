import { describe, expect, it } from 'vitest'
import { buildSummaryCardTextLines } from './summaryCardLayout'
import { createDefaultVisibility } from './summaryCardVisibility'
import type { SummaryCardRead } from '../../api/summaryCard'

const AGGREGATE: SummaryCardRead = {
  record_days: 10,
  longest_consecutive_days: 5,
  top_theme_name: '過去問演習',
  milestones: [
    { milestone_type: 'CONSECUTIVE_DAYS', milestone_key: '7', achieved_at: '2026-10-01T00:00:00Z' },
  ],
  roadmap: { progress_ratio: 0.5, is_achieved: false, overrun_days: null },
}

describe('buildSummaryCardTextLines', () => {
  it('全項目が表示・データありのとき、全行を返す', () => {
    const lines = buildSummaryCardTextLines({
      aggregate: AGGREGATE,
      visibility: createDefaultVisibility(),
      sentence: 'よく続けられました',
    })
    expect(lines.map((line) => line.key)).toEqual([
      'recordDays',
      'longestConsecutiveDays',
      'topTheme',
      'milestones',
      'aiSentence',
    ])
  })

  it('非表示の項目は出さない', () => {
    const lines = buildSummaryCardTextLines({
      aggregate: AGGREGATE,
      visibility: {
        recordDays: false,
        longestConsecutiveDays: false,
        topTheme: false,
        milestones: false,
        roadmap: true,
        aiSentence: false,
      },
      sentence: 'よく続けられました',
    })
    expect(lines).toEqual([])
  })

  it('WORKのようにtop_theme_nameがnullのときはテーマ行を出さない', () => {
    const lines = buildSummaryCardTextLines({
      aggregate: { ...AGGREGATE, top_theme_name: null },
      visibility: createDefaultVisibility(),
      sentence: null,
    })
    expect(lines.some((line) => line.key === 'topTheme')).toBe(false)
  })

  it('節目が0件のときは節目行を出さない', () => {
    const lines = buildSummaryCardTextLines({
      aggregate: { ...AGGREGATE, milestones: [] },
      visibility: createDefaultVisibility(),
      sentence: null,
    })
    expect(lines.some((line) => line.key === 'milestones')).toBe(false)
  })

  it('AI一文が未生成（null）のときはAI一文行を出さない', () => {
    const lines = buildSummaryCardTextLines({
      aggregate: AGGREGATE,
      visibility: createDefaultVisibility(),
      sentence: null,
    })
    expect(lines.some((line) => line.key === 'aiSentence')).toBe(false)
  })

  it('節目の行はresolveMilestoneMessageで組み立てた文言の配列を持つ', () => {
    const lines = buildSummaryCardTextLines({
      aggregate: AGGREGATE,
      visibility: createDefaultVisibility(),
      sentence: null,
    })
    const milestonesLine = lines.find((line) => line.key === 'milestones')
    expect(milestonesLine).toMatchObject({ values: ['7日間、連続で記録できました'] })
  })
})
