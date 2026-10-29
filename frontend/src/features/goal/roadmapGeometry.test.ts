import { describe, expect, it } from 'vitest'
import { computeRoadmapLayout, type RoadmapLayoutInput } from './roadmapGeometry'

function baseInput(overrides: Partial<RoadmapLayoutInput> = {}): RoadmapLayoutInput {
  return {
    start_date: '2026-01-01',
    goal_date: '2026-01-11',
    today_date: '2026-01-06',
    progress_ratio: 0.5,
    planned_points: [],
    actual_points: [],
    footprint_dates: [],
    replan_marks: [],
    feedback_marks: [],
    buffer_dates: [],
    ...overrides,
  }
}

describe('computeRoadmapLayout', () => {
  it('maps planned/actual points onto the 0.0-1.0 time axis', () => {
    const layout = computeRoadmapLayout(
      baseInput({
        planned_points: [
          { date: '2026-01-01', ratio: 0 },
          { date: '2026-01-11', ratio: 1 },
        ],
        actual_points: [
          { date: '2026-01-01', ratio: 0 },
          { date: '2026-01-06', ratio: 0.3 },
        ],
      }),
    )

    expect(layout.plannedPath).toEqual([
      { x: 0, y: 0 },
      { x: 1, y: 1 },
    ])
    expect(layout.actualPath).toEqual([
      { x: 0, y: 0 },
      { x: 0.5, y: 0.3 },
    ])
    expect(layout.currentPosition).toEqual({ x: 0.5, y: 0.3 })
    expect(layout.goalPosition).toEqual({ x: 1, y: 1 })
  })

  it('境界値: 記録0件でも破綻せず、現在地はprogress_ratioへフォールバックする', () => {
    const layout = computeRoadmapLayout(baseInput({ progress_ratio: 0 }))

    expect(layout.actualPath).toEqual([])
    expect(layout.plannedPath).toEqual([])
    expect(layout.currentPosition).toEqual({ x: 0.5, y: 0 })
    expect(layout.footprints).toEqual([])
  })

  it('境界値: ゴール当日は現在地とゴールが同じx位置になる', () => {
    const layout = computeRoadmapLayout(
      baseInput({ today_date: '2026-01-11', progress_ratio: 1 }),
    )

    expect(layout.currentPosition.x).toBe(1)
    expect(layout.goalPosition.x).toBe(1)
  })

  it('境界値: ゴールを過ぎた日は範囲がtoday_dateまで延び、ゴールが現在地より手前になる', () => {
    const layout = computeRoadmapLayout(
      baseInput({ today_date: '2026-01-21', progress_ratio: 1 }),
    )

    expect(layout.rangeEnd).toBe('2026-01-21')
    expect(layout.currentPosition.x).toBe(1)
    expect(layout.goalPosition.x).toBeCloseTo(0.5)
  })

  it('境界値: 進捗100%は現在地のyが1になる', () => {
    const layout = computeRoadmapLayout(
      baseInput({
        actual_points: [{ date: '2026-01-06', ratio: 1 }],
      }),
    )

    expect(layout.currentPosition.y).toBe(1)
  })

  it('境界値: 開始日と終了日が同じ（0日の範囲）場合は全て起点に揃える', () => {
    const layout = computeRoadmapLayout(
      baseInput({ start_date: '2026-01-01', goal_date: '2026-01-01', today_date: '2026-01-01' }),
    )

    expect(layout.goalPosition.x).toBe(0)
    expect(layout.currentPosition.x).toBe(0)
  })

  it('仕事目標（計画線・実績線なし）はprogress_ratioのみで現在地を決める（§0 U17）', () => {
    const layout = computeRoadmapLayout(
      baseInput({ planned_points: [], actual_points: [], progress_ratio: 0.42 }),
    )

    expect(layout.plannedPath).toEqual([])
    expect(layout.actualPath).toEqual([])
    expect(layout.currentPosition.y).toBe(0.42)
  })

  it('読書：ページ未入力の足跡は直前の実績比率を引き継ぐ', () => {
    const layout = computeRoadmapLayout(
      baseInput({
        actual_points: [{ date: '2026-01-02', ratio: 0.2 }],
        footprint_dates: [
          { date: '2026-01-01', has_input: false },
          { date: '2026-01-05', has_input: false },
        ],
      }),
    )

    expect(layout.footprints).toEqual([
      { x: 0, y: 0, date: '2026-01-01', hasInput: false },
      { x: 0.4, y: 0.2, date: '2026-01-05', hasInput: false },
    ])
  })

  it('資格：道の引き直し目印・道標・予備日をそれぞれ時間軸へ変換する', () => {
    const layout = computeRoadmapLayout(
      baseInput({
        replan_marks: [{ date: '2026-01-04', ratio: 0.2 }],
        feedback_marks: ['2026-01-03'],
        buffer_dates: ['2026-01-09'],
      }),
    )

    expect(layout.replanMarks).toEqual([{ x: 0.3, y: 0.2, date: '2026-01-04' }])
    expect(layout.feedbackMarks).toEqual([{ x: 0.2, date: '2026-01-03' }])
    expect(layout.bufferTicks).toEqual([{ x: 0.8, date: '2026-01-09' }])
  })

  it('AI未設定・フィードバック履歴0件でも道標なしで成立する（§0 要件6）', () => {
    const layout = computeRoadmapLayout(baseInput({ feedback_marks: [] }))

    expect(layout.feedbackMarks).toEqual([])
  })
})
