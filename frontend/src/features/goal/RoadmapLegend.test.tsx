import { describe, expect, it } from 'vitest'
import { render } from '@testing-library/react'
import { RoadmapLegend } from './RoadmapLegend'

describe('RoadmapLegend', () => {
  it('資格：実績・予定・道標・予備日・道の引き直しを表示する', () => {
    const { getByText } = render(<RoadmapLegend category="EXAM" />)
    expect(getByText('実際の歩み')).toBeTruthy()
    expect(getByText('計画線（予定どおり進んだ場合）')).toBeTruthy()
    expect(getByText('道標（AIフィードバックを受けた日）')).toBeTruthy()
    expect(getByText('予備日')).toBeTruthy()
    expect(getByText('道の引き直し')).toBeTruthy()
  })

  it('読書：道の引き直しは表示せず、代わりに足跡を表示する（§0 U10）', () => {
    const { getByText, queryByText } = render(<RoadmapLegend category="READING" />)
    expect(getByText('実際の歩み')).toBeTruthy()
    expect(getByText('足跡（記録のみの日）')).toBeTruthy()
    expect(queryByText('道の引き直し')).toBeNull()
  })

  it('仕事：道標と足跡のみ表示する（計画線・予備日の概念が無いため、§0 U8・U10）', () => {
    const { getByText, queryByText } = render(<RoadmapLegend category="WORK" />)
    expect(getByText('道標（AIフィードバックを受けた日）')).toBeTruthy()
    expect(getByText('足跡（記録のみの日）')).toBeTruthy()
    expect(queryByText('実際の歩み')).toBeNull()
    expect(queryByText('予備日')).toBeNull()
  })
})
