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

  it('読書：本日が予備日の場合もUI-07を使う（仕様書13.5、§0 U8訂正2026-10-30）', () => {
    const { container } = render(
      <RoadmapDiagram
        roadmap={baseRoadmap({
          category: 'READING',
          today_date: '2026-01-06',
          buffer_dates: ['2026-01-06'],
        })}
      />,
    )
    const currentMarker = container.querySelectorAll('image')[0]
    expect(currentMarker.getAttribute('href')).toBe(CHARACTER_ICONS.buffer)
  })

  it('仕事：本日が予備日と同じ日付でもUI-07にならない（仕様書13.5、仕事目標は対象外）', () => {
    const { container } = render(
      <RoadmapDiagram
        roadmap={baseRoadmap({
          category: 'WORK',
          today_date: '2026-01-06',
          buffer_dates: ['2026-01-06'],
          overrun_days: null,
        })}
      />,
    )
    const currentMarker = container.querySelectorAll('image')[0]
    expect(currentMarker.getAttribute('href')).toBe(CHARACTER_ICONS.normal)
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

  it('計画線・実績線は2点以上あればpolylineとして描かれる', () => {
    const { container } = render(
      <RoadmapDiagram
        roadmap={baseRoadmap({
          planned_points: [
            { date: '2026-01-01', ratio: 0 },
            { date: '2026-01-11', ratio: 1 },
          ],
          actual_points: [
            { date: '2026-01-01', ratio: 0 },
            { date: '2026-01-06', ratio: 0.5 },
          ],
        })}
      />,
    )
    expect(container.querySelectorAll('polyline')).toHaveLength(2)
  })

  it('足跡（記録のみの日）は円で描かれる（§0 要件2）', () => {
    const { container } = render(
      <RoadmapDiagram
        roadmap={baseRoadmap({
          actual_points: [{ date: '2026-01-01', ratio: 0.2 }],
          footprint_dates: [
            { date: '2026-01-02', has_input: false },
            { date: '2026-01-03', has_input: true },
          ],
        })}
      />,
    )
    expect(container.querySelectorAll('circle').length).toBeGreaterThan(1)
  })

  it('道の引き直し目印（EXAM）は縦線で描かれる（§0 U6）', () => {
    const { container } = render(
      <RoadmapDiagram
        roadmap={baseRoadmap({ replan_marks: [{ date: '2026-01-04', ratio: 0.3 }] })}
      />,
    )
    expect(container.querySelectorAll('line').length).toBeGreaterThan(1)
  })

  it('仕事目標は現在地・ゴールが常に地面の高さに置かれる（§0 U17）', () => {
    const { container } = render(
      <RoadmapDiagram roadmap={baseRoadmap({ category: 'WORK', overrun_days: null })} />,
    )
    const [currentMarker, goalMarker] = container.querySelectorAll('image')
    // VIEW_HEIGHT=64, TOP_MARGIN=8, PLOT_HEIGHT=38, ground = 8 + 38*(1-0) = 46, 半幅5を引く。
    expect(currentMarker.getAttribute('y')).toBe('41')
    expect(goalMarker.getAttribute('y')).toBe('41')
  })

  it('スタート・ゴールに名称と日付のラベルを表示する（利用者フィードバック対応、2026-11-01）', () => {
    const { container } = render(<RoadmapDiagram roadmap={baseRoadmap()} />)
    const texts = Array.from(container.querySelectorAll('text')).map((el) => el.textContent)
    expect(texts).toContain('スタート')
    expect(texts).toContain('1/1')
    expect(texts).toContain('ゴール')
    expect(texts).toContain('1/11')
  })

  it('ゴール未到達時は輪を表示し、達成時は輪を消す', () => {
    const { container: notAchieved } = render(
      <RoadmapDiagram roadmap={baseRoadmap({ is_achieved: false })} />,
    )
    expect(notAchieved.querySelectorAll('circle[stroke-dasharray="1.5 1"]').length).toBe(1)

    const { container: achieved } = render(
      <RoadmapDiagram roadmap={baseRoadmap({ is_achieved: true, progress_ratio: 1 })} />,
    )
    expect(achieved.querySelectorAll('circle[stroke-dasharray="1.5 1"]').length).toBe(0)
  })

  it('計画と実績にズレがある場合、本日位置に縦線（ズレの目印）を表示する（仕様書13.8）', () => {
    const { container } = render(
      <RoadmapDiagram
        roadmap={baseRoadmap({
          planned_points: [
            { date: '2026-01-01', ratio: 0 },
            { date: '2026-01-11', ratio: 1 },
          ],
          actual_points: [{ date: '2026-01-06', ratio: 0.2 }],
        })}
      />,
    )
    const gapLine = container.querySelector('line[stroke-dasharray="1 1"]')
    expect(gapLine).toBeTruthy()
    // 計画(0.5)より実績(0.2)が低い＝遅れているため、強調色（ライトモードの--danger-text）になる。
    expect(gapLine?.getAttribute('stroke')).toBe('#dc2626')
  })

  it('計画より実績が進んでいる場合は強調色にならない', () => {
    const { container } = render(
      <RoadmapDiagram
        roadmap={baseRoadmap({
          planned_points: [
            { date: '2026-01-01', ratio: 0 },
            { date: '2026-01-11', ratio: 1 },
          ],
          actual_points: [{ date: '2026-01-06', ratio: 0.8 }],
        })}
      />,
    )
    const gapLine = container.querySelector('line[stroke-dasharray="1 1"]')
    expect(gapLine?.getAttribute('stroke')).not.toBe('#dc2626')
  })

  it('計画と実績がほぼ同じ場合はズレの目印を表示しない', () => {
    const { container } = render(
      <RoadmapDiagram
        roadmap={baseRoadmap({
          planned_points: [
            { date: '2026-01-01', ratio: 0 },
            { date: '2026-01-11', ratio: 1 },
          ],
          actual_points: [{ date: '2026-01-06', ratio: 0.5 }],
        })}
      />,
    )
    expect(container.querySelector('line[stroke-dasharray="1 1"]')).toBeNull()
  })

  it('仕事目標は計画線が無いためズレの目印を表示しない', () => {
    const { container } = render(
      <RoadmapDiagram roadmap={baseRoadmap({ category: 'WORK', overrun_days: null })} />,
    )
    expect(container.querySelector('line[stroke-dasharray="1 1"]')).toBeNull()
  })

  it('仕事目標は現在地までの経過を地面の色付き帯で示す（§0 U17）', () => {
    const { container } = render(
      <RoadmapDiagram roadmap={baseRoadmap({ category: 'WORK', overrun_days: null })} />,
    )
    // x=50%地点（開始〜終了10日のうち5日目）。
    const elapsedLine = container.querySelector('line[x2="50"]')
    expect(elapsedLine).toBeTruthy()
  })
})
