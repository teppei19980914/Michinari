import { useEffect, useState } from 'react'
import { t } from '../../locales/t'
import { ROUTES } from '../../constants/routes'
import { CHARACTER_ICONS } from '../../constants/characterIcons'
import {
  cycleSeriesColor,
  resolveAxisLineColor,
  resolveDelayedLineColor,
  resolveGridLineColor,
  resolvePlanLineColor,
  THRESHOLD_LINE_COLOR,
} from '../analytics/chartColors'
import { usePrefersReducedMotion } from '../../hooks/usePrefersReducedMotion'
import { formatDateTick } from '../analytics/formatPeriod'
import {
  computeRoadmapLayout,
  type LayoutFootprint,
  type LayoutMark,
  type LayoutTick,
  type RoadmapLayoutInput,
} from './roadmapGeometry'
import { resolveScheduleStatusIcon } from './scheduleStatus'
import { buildRoadmapSummaryText } from './roadmapSummaryText'
import type { GoalCategory } from '../../api/goals'

export type RoadmapDiagramInput = RoadmapLayoutInput & {
  category: GoalCategory
  is_achieved: boolean
  overrun_days: number | null
}

type RoadmapDiagramProps = {
  roadmap: RoadmapDiagramInput
  /** 道標クリックでの遷移を有効にするか（ダッシュボード縮小版は読み取り専用、§0 U2）。 */
  interactive?: boolean
}

const VIEW_WIDTH = 100
const TOP_MARGIN = 8
// 下余白は「スタート/ゴール」の2行ラベル（ラベル名＋日付）を収める分、従来より広く取る
// （利用者フィードバック：図だけでは何が何を表しているか分かりづらい、2026-11-01）。
const BOTTOM_MARGIN = 18
const PLOT_HEIGHT = 38
const VIEW_HEIGHT = TOP_MARGIN + PLOT_HEIGHT + BOTTOM_MARGIN
const ICON_SIZE = 10
const LANDMARK_LABEL_SIZE = 4.2
const LANDMARK_DATE_SIZE = 3.6

function toSvgX(xFraction: number): number {
  return xFraction * VIEW_WIDTH
}

function toSvgY(yRatio: number): number {
  return TOP_MARGIN + PLOT_HEIGHT * (1 - yRatio)
}

function pointsAttr(points: { x: number; y: number }[]): string {
  return points.map((p) => `${toSvgX(p.x)},${toSvgY(p.y)}`).join(' ')
}

/** 現在地のキャラクターアイコン（UI-01〜UI-04/UI-07/UI-11）を状態から選ぶ（§0 要件3・U7・U8）。
 * 予備日（UI-07）は仕様書13.5のとおり資格試験・読書目標が対象（仕事目標のみ対象外、
 * §0 U8訂正・2026-10-30。バッファ日はカテゴリに依存しないカレンダー概念のため、
 * スケジュール状態アイコン〈UI-02〜04、資格試験のみ〉より先に判定する）。 */
function resolveCurrentIcon(roadmap: RoadmapDiagramInput): string {
  if (roadmap.is_achieved) {
    return CHARACTER_ICONS.achieved
  }
  if (roadmap.category !== 'WORK' && roadmap.buffer_dates.includes(roadmap.today_date)) {
    return CHARACTER_ICONS.buffer
  }
  if (roadmap.category !== 'EXAM') {
    // 読書・仕事は進捗状態アイコンを新設しないため常にUI-01（§0 U7）。
    return CHARACTER_ICONS.normal
  }
  return resolveScheduleStatusIcon(roadmap.overrun_days) ?? CHARACTER_ICONS.normal
}

/** 予備日の目盛り（UI-07相当、資格のみ。§0 U8。RoadmapDiagram本体の行数分割のため抽出）。 */
function BufferTicks({ ticks, groundY }: { ticks: LayoutTick[]; groundY: number }) {
  return (
    <>
      {ticks.map((tick) => (
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
    </>
  )
}

/** 足跡（記録はあるが定量入力が無い日は薄く表示。§0 要件2）。 */
function FootprintMarks({ footprints }: { footprints: LayoutFootprint[] }) {
  return (
    <>
      {footprints.map((footprint) => (
        <circle
          key={`footprint-${footprint.date}`}
          cx={toSvgX(footprint.x)}
          cy={toSvgY(footprint.y)}
          r={1.2}
          fill={cycleSeriesColor(0)}
          opacity={footprint.hasInput ? 0.9 : 0.4}
        />
      ))}
    </>
  )
}

/** 道の引き直し目印（EXAMのみ。§0 U10によりREADING/WORKは常に空配列）。 */
function ReplanMarks({ marks }: { marks: LayoutMark[] }) {
  return (
    <>
      {marks.map((mark) => (
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
    </>
  )
}

/** 道標（AIフィードバック日）。詳細版（interactive）のみ日次報告閲覧へのリンクにする
 * （ダッシュボード縮小版はGoalRoadmapMini側で描くため、ここは常にinteractive、§0 U2・U5）。 */
function FeedbackMarks({
  marks,
  groundY,
  interactive,
}: {
  marks: LayoutTick[]
  groundY: number
  interactive: boolean
}) {
  return (
    <>
      {marks.map((mark) =>
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
    </>
  )
}

/** スタート／ゴールの着地点ラベル（ラベル名＋日付の2行）。x=0付近は左詰め、それ以外は
 * 右詰めで描き、画面端での文字切れを避ける（スタートは常にx=0、ゴールは通常x=100付近だが
 * ゴール超過等の境界ケースでも右詰めなら切れない）。 */
function LandmarkLabel({
  x,
  labelText,
  dateText,
  align,
}: {
  x: number
  labelText: string
  dateText: string
  align: 'start' | 'end'
}) {
  const labelY = TOP_MARGIN + PLOT_HEIGHT + 7
  return (
    <>
      <text
        x={x}
        y={labelY}
        textAnchor={align}
        fontSize={LANDMARK_LABEL_SIZE}
        fill={resolveAxisLineColor()}
      >
        {labelText}
      </text>
      <text
        x={x}
        y={labelY + LANDMARK_DATE_SIZE + 1.5}
        textAnchor={align}
        fontSize={LANDMARK_DATE_SIZE}
        fill={resolveGridLineColor()}
      >
        {dateText}
      </text>
    </>
  )
}

/** 本日時点の「計画線と実績線のズレ」を縦線で直接示す（仕様書13.8「計画との差は図中の
 * 計画線と実績線のズレ自体で表現する」）。遅れている場合のみ強調色にする
 * （ForecastTab.tsxと同じ「遅延のみ強調」の配色方針、CLAUDE.md DRYの原則）。 */
function GapIndicator({
  x,
  plannedY,
  actualY,
}: {
  x: number
  plannedY: number
  actualY: number
}) {
  if (Math.abs(plannedY - actualY) < 0.1) {
    return null
  }
  const isBehind = actualY < plannedY
  return (
    <line
      x1={x}
      y1={toSvgY(plannedY)}
      x2={x}
      y2={toSvgY(actualY)}
      stroke={isBehind ? resolveDelayedLineColor() : cycleSeriesColor(0)}
      strokeWidth={0.8}
      strokeDasharray="1 1"
      opacity={0.8}
    />
  )
}

/** 地面の基準線。仕事目標のみ、評価期間に対する経過をこの帯の色付き部分で示す
 * （§0 U17。進捗量の概念が無いWORKの図に何も表示が無く分かりづらいという利用者
 * フィードバックへの対応、2026-11-01。RoadmapDiagram本体の行数分割のため抽出）。 */
function GroundLine({
  groundY,
  isFlatRoad,
  currentX,
}: {
  groundY: number
  isFlatRoad: boolean
  currentX: number
}) {
  return (
    <>
      <line x1={0} y1={groundY} x2={VIEW_WIDTH} y2={groundY} stroke={resolveAxisLineColor()} strokeWidth={0.5} />
      {isFlatRoad && (
        <line x1={0} y1={groundY} x2={currentX} y2={groundY} stroke={cycleSeriesColor(0)} strokeWidth={1.5} />
      )}
    </>
  )
}

/** ゴール地点の表示一式（輪＋アイコン）とスタート／ゴールの着地点ラベル
 * （RoadmapDiagram本体の行数分割のため抽出）。 */
function Landmarks({
  goalX,
  goalY,
  isAchieved,
  startDate,
  goalDate,
}: {
  goalX: number
  goalY: number
  isAchieved: boolean
  startDate: string
  goalDate: string
}) {
  return (
    <>
      {/* ゴール未到達時は輪（的）で「まだ到達していない目印」であることを明示する
          （不透明度のみでの表現は壊れた画像のように見えるという利用者フィードバック、
          2026-11-01）。 */}
      {!isAchieved && (
        <circle
          cx={goalX}
          cy={goalY}
          r={ICON_SIZE / 2 + 1.2}
          fill="none"
          stroke={resolveAxisLineColor()}
          strokeWidth={0.6}
          strokeDasharray="1.5 1"
        />
      )}
      <image
        href={isAchieved ? CHARACTER_ICONS.achieved : CHARACTER_ICONS.normal}
        x={goalX - ICON_SIZE / 2}
        y={goalY - ICON_SIZE / 2}
        width={ICON_SIZE}
        height={ICON_SIZE}
        opacity={isAchieved ? 1 : 0.85}
        aria-hidden="true"
      />
      <LandmarkLabel
        x={0}
        align="start"
        labelText={t('goals.roadmap.startLabel')}
        dateText={formatDateTick(startDate)}
      />
      <LandmarkLabel
        x={goalX}
        align="end"
        labelText={t('goals.roadmap.goalLabel')}
        dateText={formatDateTick(goalDate)}
      />
    </>
  )
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
    // 初回表示後にのみ現在地まで歩くアニメーションを発生させる（§0 要件5）。
    // prefersReducedMotionがオンの場合は初期状態が既にtrueのため、ここでは何もしない。
    if (prefersReducedMotion) {
      return
    }
    const frameId = requestAnimationFrame(() => setHasWalkedIn(true))
    return () => cancelAnimationFrame(frameId)
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
  const goalX = toSvgX(layout.goalPosition.x)
  const goalY = toSvgY(goalYRatio)
  const currentX = toSvgX(layout.currentPosition.x)

  return (
    <svg
      viewBox={`0 0 ${VIEW_WIDTH} ${VIEW_HEIGHT}`}
      role="img"
      aria-label={summaryText}
      className="h-full w-full"
    >
      <GroundLine groundY={groundY} isFlatRoad={isFlatRoad} currentX={currentX} />

      <BufferTicks ticks={layout.bufferTicks} groundY={groundY} />

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
      {!isFlatRoad && layout.plannedAtCurrent !== null && (
        <GapIndicator x={currentX} plannedY={layout.plannedAtCurrent} actualY={currentYRatio} />
      )}

      <FootprintMarks footprints={layout.footprints} />
      <ReplanMarks marks={layout.replanMarks} />
      <FeedbackMarks marks={layout.feedbackMarks} groundY={groundY} interactive={interactive} />

      <image
        href={currentIcon}
        x={markerX - ICON_SIZE / 2}
        y={markerY - ICON_SIZE / 2}
        width={ICON_SIZE}
        height={ICON_SIZE}
        style={transitionStyle}
        aria-hidden="true"
      />

      <Landmarks
        goalX={goalX}
        goalY={goalY}
        isAchieved={roadmap.is_achieved}
        startDate={roadmap.start_date}
        goalDate={roadmap.goal_date}
      />
    </svg>
  )
}
