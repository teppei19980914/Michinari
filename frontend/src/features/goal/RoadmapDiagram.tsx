import { useEffect, useState } from 'react'
import { t } from '../../locales/t'
import { ROUTES } from '../../constants/routes'
import { CHARACTER_ICONS } from '../../constants/characterIcons'
import {
  cycleSeriesColor,
  resolveAxisLineColor,
  resolveGridLineColor,
  resolvePlanLineColor,
  THRESHOLD_LINE_COLOR,
} from '../analytics/chartColors'
import { usePrefersReducedMotion } from '../../hooks/usePrefersReducedMotion'
import { computeRoadmapLayout, type RoadmapLayoutInput } from './roadmapGeometry'
import { resolveScheduleStatusIcon } from './scheduleStatus'
import { buildRoadmapSummaryText } from './roadmapSummaryText'
import type { GoalCategory } from '../../api/goals'

export type RoadmapDiagramInput = RoadmapLayoutInput & {
  category: GoalCategory
  is_achieved: boolean
}

type RoadmapDiagramProps = {
  roadmap: RoadmapDiagramInput
  /** 道標クリックでの遷移を有効にするか（ダッシュボード縮小版は読み取り専用、§0 U2）。 */
  interactive?: boolean
}

const VIEW_WIDTH = 100
const VIEW_HEIGHT = 56
const TOP_MARGIN = 8
const BOTTOM_MARGIN = 10
const PLOT_HEIGHT = VIEW_HEIGHT - TOP_MARGIN - BOTTOM_MARGIN
const ICON_SIZE = 10

function toSvgX(xFraction: number): number {
  return xFraction * VIEW_WIDTH
}

function toSvgY(yRatio: number): number {
  return TOP_MARGIN + PLOT_HEIGHT * (1 - yRatio)
}

function pointsAttr(points: { x: number; y: number }[]): string {
  return points.map((p) => `${toSvgX(p.x)},${toSvgY(p.y)}`).join(' ')
}

/** 現在地のキャラクターアイコン（UI-01〜UI-04/UI-07/UI-11）を状態から選ぶ（§0 要件3・U7・U8）。 */
function resolveCurrentIcon(roadmap: RoadmapDiagramInput): string {
  if (roadmap.is_achieved) {
    return CHARACTER_ICONS.achieved
  }
  if (roadmap.category !== 'EXAM') {
    // 読書・仕事は常にUI-01（§0 U7：進捗状態アイコンは新設しない）。
    return CHARACTER_ICONS.normal
  }
  if (roadmap.buffer_dates.includes(roadmap.today_date)) {
    // 本日が予備日の場合はUI-07（§0 要件3・U8、資格のみ）。
    return CHARACTER_ICONS.buffer
  }
  return resolveScheduleStatusIcon(roadmap.overrun_days) ?? CHARACTER_ICONS.normal
}

/**
 * 道のりマップの図（開発Todo_道のりマップ_v1.0.md §4）。新しいグラフ用ライブラリは追加せず
 * 生SVGで描く（§0 要件5）。`GoalRoadmapMini`（縮小版）・`GoalRoadmapTab`（詳細版）の両方が
 * この描画ロジックを共有する（DRYの原則）。
 */
export function RoadmapDiagram({ roadmap, interactive = false }: RoadmapDiagramProps) {
  const layout = computeRoadmapLayout(roadmap)
  const prefersReducedMotion = usePrefersReducedMotion()
  const [hasWalkedIn, setHasWalkedIn] = useState(prefersReducedMotion)

  useEffect(() => {
    if (prefersReducedMotion) {
      setHasWalkedIn(true)
      return
    }
    // 初回表示後にのみ現在地まで歩くアニメーションを発生させる（§0 要件5）。
    setHasWalkedIn(true)
  }, [prefersReducedMotion])

  const summaryText = buildRoadmapSummaryText({
    category: roadmap.category,
    progressRatio: roadmap.progress_ratio,
    overrunDays: roadmap.overrun_days,
    isAchieved: roadmap.is_achieved,
  })

  const currentIcon = resolveCurrentIcon(roadmap)
  // 仕事は進捗量（標高）の概念が無いため、現在地・ゴールとも常に地面の高さに置く
  // （§0 U17。xのみ経過日数の割合・ゴール日で変わる）。
  const isFlatRoad = roadmap.category === 'WORK'
  const currentYRatio = isFlatRoad ? 0 : layout.currentPosition.y
  const goalYRatio = isFlatRoad ? 0 : 1
  const markerX = hasWalkedIn ? toSvgX(layout.currentPosition.x) : toSvgX(layout.startPosition.x)
  const markerY = hasWalkedIn ? toSvgY(currentYRatio) : toSvgY(0)
  const transitionStyle = prefersReducedMotion
    ? undefined
    : { transition: 'x 0.6s ease-out, y 0.6s ease-out' }

  const groundY = toSvgY(0)

  return (
    <svg
      viewBox={`0 0 ${VIEW_WIDTH} ${VIEW_HEIGHT}`}
      role="img"
      aria-label={summaryText}
      className="h-full w-full"
    >
      <line
        x1={0}
        y1={groundY}
        x2={VIEW_WIDTH}
        y2={groundY}
        stroke={resolveAxisLineColor()}
        strokeWidth={0.5}
      />

      {layout.bufferTicks.map((tick) => (
        <line
          key={`buffer-${tick.date}`}
          x1={toSvgX(tick.x)}
          y1={groundY - 2}
          x2={toSvgX(tick.x)}
          y2={groundY + 2}
          stroke={resolveGridLineColor()}
          strokeWidth={0.8}
        />
      ))}

      {layout.plannedPath.length > 1 && (
        <polyline
          points={pointsAttr(layout.plannedPath)}
          fill="none"
          stroke={resolvePlanLineColor()}
          strokeWidth={1}
          strokeDasharray="3 2"
        />
      )}
      {layout.actualPath.length > 1 && (
        <polyline
          points={pointsAttr(layout.actualPath)}
          fill="none"
          stroke={cycleSeriesColor(0)}
          strokeWidth={1.2}
        />
      )}

      {layout.footprints.map((footprint) => (
        <circle
          key={`footprint-${footprint.date}`}
          cx={toSvgX(footprint.x)}
          cy={toSvgY(footprint.y)}
          r={1.2}
          fill={cycleSeriesColor(0)}
          opacity={footprint.hasInput ? 0.9 : 0.4}
        />
      ))}

      {layout.replanMarks.map((mark) => (
        <line
          key={`replan-${mark.date}`}
          x1={toSvgX(mark.x)}
          y1={toSvgY(0)}
          x2={toSvgX(mark.x)}
          y2={toSvgY(1)}
          stroke={THRESHOLD_LINE_COLOR}
          strokeWidth={0.6}
          strokeDasharray="1.5 1.5"
        />
      ))}

      {layout.feedbackMarks.map((mark) =>
        interactive ? (
          <a
            key={`feedback-${mark.date}`}
            href={ROUTES.dailyReportView(mark.date)}
            aria-label={t('goals.roadmap.feedbackMarkLabel')}
          >
            <circle cx={toSvgX(mark.x)} cy={groundY} r={1.6} fill={cycleSeriesColor(2)} />
          </a>
        ) : (
          <circle
            key={`feedback-${mark.date}`}
            cx={toSvgX(mark.x)}
            cy={groundY}
            r={1.6}
            fill={cycleSeriesColor(2)}
          />
        ),
      )}

      <image
        href={currentIcon}
        x={markerX - ICON_SIZE / 2}
        y={markerY - ICON_SIZE / 2}
        width={ICON_SIZE}
        height={ICON_SIZE}
        style={transitionStyle}
        aria-hidden="true"
      />

      <image
        href={roadmap.is_achieved ? CHARACTER_ICONS.achieved : CHARACTER_ICONS.normal}
        x={toSvgX(layout.goalPosition.x) - ICON_SIZE / 2}
        y={toSvgY(goalYRatio) - ICON_SIZE / 2}
        width={ICON_SIZE}
        height={ICON_SIZE}
        opacity={roadmap.is_achieved ? 1 : 0.5}
        aria-hidden="true"
      />
    </svg>
  )
}
