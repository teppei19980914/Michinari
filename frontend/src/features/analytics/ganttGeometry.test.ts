import { describe, expect, it } from 'vitest'
import { computeGanttLayout } from './ganttGeometry'

describe('computeGanttLayout', () => {
  it('positions a single material spanning the whole range at 0%-100%', () => {
    const { entries } = computeGanttLayout(
      [{ material_id: 1, start_date: '2026-01-01', due_date: '2026-01-11', progress_rate: 0.5 }],
      '2026-01-06',
    )

    expect(entries).toEqual([
      { material_id: 1, leftPercent: 0, widthPercent: 100, progressWidthPercent: 50 },
    ])
  })

  it('positions a material starting after the range start with a left offset', () => {
    const { entries } = computeGanttLayout(
      [
        { material_id: 1, start_date: '2026-01-01', due_date: '2026-01-21', progress_rate: 0 },
        { material_id: 2, start_date: '2026-01-11', due_date: '2026-01-21', progress_rate: 0 },
      ],
      '2026-01-01',
    )

    // 全体範囲は1/1〜1/21(20日)。教材2は1/11開始 -> 10日後 -> 50%左オフセット
    const material2 = entries.find((e) => e.material_id === 2)
    expect(material2?.leftPercent).toBeCloseTo(50)
    expect(material2?.widthPercent).toBeCloseTo(50)
  })

  it('clamps progress_rate above 1 so the filled width never exceeds the bar', () => {
    const { entries } = computeGanttLayout(
      [{ material_id: 1, start_date: '2026-01-01', due_date: '2026-01-11', progress_rate: 1.5 }],
      '2026-01-01',
    )

    expect(entries[0].progressWidthPercent).toBe(100)
  })

  it('returns null todayPercent when today is outside the material range', () => {
    const { todayPercent } = computeGanttLayout(
      [{ material_id: 1, start_date: '2026-01-01', due_date: '2026-01-11', progress_rate: 0 }],
      '2026-02-01',
    )

    expect(todayPercent).toBeNull()
  })

  it('境界値: falls back to full-width bars when the overall range spans zero days', () => {
    const { entries, todayPercent } = computeGanttLayout(
      [{ material_id: 1, start_date: '2026-01-01', due_date: '2026-01-01', progress_rate: 0.3 }],
      '2026-01-01',
    )

    expect(entries).toEqual([
      { material_id: 1, leftPercent: 0, widthPercent: 100, progressWidthPercent: 30 },
    ])
    expect(todayPercent).toBeNull()
  })

  it('returns empty layout when there are no materials', () => {
    expect(computeGanttLayout([], '2026-01-01')).toEqual({ entries: [], todayPercent: null })
  })
})
