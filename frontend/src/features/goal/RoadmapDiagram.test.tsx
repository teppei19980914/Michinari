import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render } from '@testing-library/react'
import { RoadmapDiagram, type RoadmapDiagramInput } from './RoadmapDiagram'
import { CHARACTER_ICONS } from '../../constants/characterIcons'

function mockMatchMedia(matches: boolean) {
  vi.stubGlobal(
    'matchMedia',
    vi.fn().mockImplementation(() => ({
      matches,
      media: '(prefers-reduced-motion: reduce)',
      addEventListener: () => {},
      removeEventListener: () => {},
    })),
  )
}

function baseRoadmap(overrides: Partial<RoadmapDiagramInput> = {}): RoadmapDiagramInput {
  return {
    category: 'EXAM',
    start_date: '2026-01-01',
    goal_date: '2026-01-11',
    today_date: '2026-01-06',
    progress_ratio: 0.5,
    is_achieved: false,
    planned_points: [],
    actual_points: [],
    footprint_dates: [],
    replan_marks: [],
    feedback_marks: [],
    buffer_dates: [],
    overrun_days: null,
    ...overrides,
  }
}

beforeEach(() => {
  mockMatchMedia(true)
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe('RoadmapDiagram', () => {
  it('図にrole="img"とaria-label（要約文言）を付ける', () => {
    const { getByRole } = render(
      <RoadmapDiagram roadmap={baseRoadmap({ overrun_days: 3 })} />,
    )
    expect(getByRole('img', { name: '全体の50%、予定より3日遅れです' })).toBeTruthy()
  })

  it('達成時はゴールにUI-11（達成アイコン）を使う', () => {
    const { container } = render(
      <RoadmapDiagram roadmap={baseRoadmap({ is_achieved: true, progress_ratio: 1 })} />,
    )
    const images = container.querySelectorAll('image')
    expect(Array.from(images).some((img) => img.getAttribute('href') === CHARACTER_ICONS.achieved)).toBe(
      true,
    )
  })

  it('読書・仕事は現在地が常にUI-01（normal）になる（§0 U7）', () => {
    const { container } = render(
      <RoadmapDiagram roadmap={baseRoadmap({ category: 'READING', overrun_days: null })} />,
    )
    const currentMarker = container.querySelectorAll('image')[0]
    expect(currentMarker.getAttribute('href')).toBe(CHARACTER_ICONS.normal)
  })

  it('資格：本日が予備日の場合はUI-07を使う（§0 要件3・U8）', () => {
    const { container } = render(
      <RoadmapDiagram
        roadmap={baseRoadmap({ today_date: '2026-01-06', buffer_dates: ['2026-01-06'] })}
      />,
    )
    const currentMarker = container.querySelectorAll('image')[0]
    expect(currentMarker.getAttribute('href')).toBe(CHARACTER_ICONS.buffer)
  })

  it('道標は非対話版では<a>にならない', () => {
    const { container } = render(
      <RoadmapDiagram roadmap={baseRoadmap({ feedback_marks: ['2026-01-03'] })} interactive={false} />,
    )
    expect(container.querySelector('a')).toBeNull()
    expect(container.querySelector('circle')).toBeTruthy()
  })

  it('道標は対話版では日次報告閲覧へのリンクになる（§4共通）', () => {
    const { container } = render(
      <RoadmapDiagram roadmap={baseRoadmap({ feedback_marks: ['2026-01-03'] })} interactive />,
    )
    const link = container.querySelector('a')
    expect(link?.getAttribute('href')).toBe('/records/2026-01-03/view')
  })

  it('AI未設定・フィードバック履歴0件でも道標なしで図が成立する（§0 要件6）', () => {
    const { container } = render(
      <RoadmapDiagram roadmap={baseRoadmap({ feedback_marks: [] })} interactive />,
    )
    expect(container.querySelector('a')).toBeNull()
  })

  it('prefers-reduced-motionがオンの場合は現在地アイコンが最初から現在地にある', () => {
    mockMatchMedia(true)
    const { container } = render(<RoadmapDiagram roadmap={baseRoadmap()} />)
    const currentMarker = container.querySelectorAll('image')[0]
    // x=50%地点（開始〜終了10日のうち5日目）。アイコン幅10のため中心から半幅を引く。
    expect(currentMarker.getAttribute('x')).toBe('45')
  })

  it('prefers-reduced-motionがオフの場合は現在地アイコンの移動にtransitionを付ける', () => {
    mockMatchMedia(false)
    const { container } = render(<RoadmapDiagram roadmap={baseRoadmap()} />)
    const currentMarker = container.querySelectorAll('image')[0]
    expect(currentMarker.getAttribute('style')).toContain('transition')
  })

  it('prefers-reduced-motionがオンの場合は現在地アイコンの移動にtransitionを付けない', () => {
    mockMatchMedia(true)
    const { container } = render(<RoadmapDiagram roadmap={baseRoadmap()} />)
    const currentMarker = container.querySelectorAll('image')[0]
    expect(currentMarker.getAttribute('style')).toBeNull()
  })

  it('境界値: 記録0件でも破綻せず描画できる', () => {
    const { container } = render(<RoadmapDiagram roadmap={baseRoadmap()} />)
    expect(container.querySelector('svg')).toBeTruthy()
  })

  it('仕事目標は現在地・ゴールが常に地面の高さに置かれる（§0 U17）', () => {
    const { container } = render(
      <RoadmapDiagram roadmap={baseRoadmap({ category: 'WORK', overrun_days: null })} />,
    )
    const [currentMarker, goalMarker] = container.querySelectorAll('image')
    // VIEW_HEIGHT=56, TOP_MARGIN=8, PLOT_HEIGHT=38, ground = 8 + 38*(1-0) = 46, 半幅5を引く。
    expect(currentMarker.getAttribute('y')).toBe('41')
    expect(goalMarker.getAttribute('y')).toBe('41')
  })
})
