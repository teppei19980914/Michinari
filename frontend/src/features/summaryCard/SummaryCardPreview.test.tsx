import { describe, expect, it } from 'vitest'
import { render } from '@testing-library/react'
import { SummaryCardPreview } from './SummaryCardPreview'
import { createDefaultVisibility } from './summaryCardVisibility'
import type { SummaryCardRead } from '../../api/summaryCard'

const AGGREGATE: SummaryCardRead = {
  record_days: 42,
  longest_consecutive_days: 10,
  top_theme_name: '過去問演習',
  milestones: [
    { milestone_type: 'CONSECUTIVE_DAYS', milestone_key: '7', achieved_at: '2026-10-01T00:00:00Z' },
  ],
  roadmap: { progress_ratio: 0.6, is_achieved: false, overrun_days: null },
}

const PERIOD = { dateFrom: '2026-01-01', dateTo: '2026-11-13' }

describe('SummaryCardPreview', () => {
  it('role="img"で描画し、目標名・期間・各項目の値を含む', () => {
    const { getAllByRole, getByText } = render(
      <SummaryCardPreview
        goalName="基本情報技術者試験"
        category="EXAM"
        period={PERIOD}
        aggregate={AGGREGATE}
        visibility={createDefaultVisibility()}
        sentence="よく書き続けられました"
      />,
    )
    // カード本体＋道のりマップ縮小図（GoalRoadmapMini）の2件がrole="img"になる。
    expect(getAllByRole('img').length).toBe(2)
    expect(getByText('基本情報技術者試験')).toBeTruthy()
    expect(getByText('過去問演習')).toBeTruthy()
    expect(getByText('よく書き続けられました')).toBeTruthy()
  })

  it('AI一文が未生成（null）のときは当該行を出さない', () => {
    const { queryByText } = render(
      <SummaryCardPreview
        goalName="基本情報技術者試験"
        category="EXAM"
        period={PERIOD}
        aggregate={AGGREGATE}
        visibility={createDefaultVisibility()}
        sentence={null}
      />,
    )
    expect(queryByText('よく書き続けられました')).toBeNull()
  })

  it('非表示トグルの項目は出さない（道のりマップ縮小図も含む）', () => {
    const { queryByText, container } = render(
      <SummaryCardPreview
        goalName="基本情報技術者試験"
        category="EXAM"
        period={PERIOD}
        aggregate={AGGREGATE}
        visibility={{ ...createDefaultVisibility(), topTheme: false, roadmap: false }}
        sentence={null}
      />,
    )
    expect(queryByText('過去問演習')).toBeNull()
    // 道のりマップ縮小図（GoalRoadmapMini）はネストしたsvgとして描かれるため、
    // 非表示時はカード本体のsvg1件のみになる。
    expect(container.querySelectorAll('svg').length).toBe(1)
  })

  it('WORK（テーマ項目が常にnull）でもテーマ行を出さない', () => {
    const { queryByText } = render(
      <SummaryCardPreview
        goalName="〇〇案件"
        category="WORK"
        period={PERIOD}
        aggregate={{ ...AGGREGATE, top_theme_name: null, milestones: [] }}
        visibility={createDefaultVisibility()}
        sentence={null}
      />,
    )
    expect(queryByText('過去問演習')).toBeNull()
  })
})
