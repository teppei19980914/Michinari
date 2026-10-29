import { CHARACTER_ICONS } from '../../constants/characterIcons'
import { cycleSeriesColor, resolveAxisLineColor } from '../analytics/chartColors'
import { resolveScheduleStatusIcon } from './scheduleStatus'
import { buildRoadmapSummaryText } from './roadmapSummaryText'
import type { GoalCategory } from '../../api/goals'

export type GoalRoadmapMiniProps = {
  category: GoalCategory
  /** `GET /dashboard`の`GoalCardRead.roadmap_progress_ratio`（開発Todo_道のりマップ_v1.0.md
   * §0 U15）。線データ・目印データは持たず、進捗比率のみで「スタート→現在地→ゴール」の
   * 概観を示す軽量な縮小版（詳細な計画線・足跡・道標は詳細版`GoalRoadmapTab`のみで描く）。 */
  progressRatio: number | null
  isAchieved: boolean
  overrunDays: number | null
}

const VIEW_WIDTH = 100
const VIEW_HEIGHT = 24
const ROAD_Y = 18
const ICON_SIZE = 12

/**
 * 道のりマップの縮小版（ダッシュボードの目標カード用）。読み取り専用・単独コンポーネントで、
 * 後続開発（ふりかえりまとめ・社内共有カード）でも再利用できるよう、API呼び出しを持たず
 * props（軽量フィールド）のみで描画する（§0 U2・U15）。
 */
export function GoalRoadmapMini({
  category,
  progressRatio,
  isAchieved,
  overrunDays,
}: GoalRoadmapMiniProps) {
  const ratio = Math.min(1, Math.max(0, progressRatio ?? 0))
  const summaryText = buildRoadmapSummaryText({
    category,
    progressRatio: ratio,
    overrunDays,
    isAchieved,
  })
  const currentIcon = isAchieved
    ? CHARACTER_ICONS.achieved
    : category === 'EXAM'
      ? resolveScheduleStatusIcon(overrunDays) ?? CHARACTER_ICONS.normal
      : CHARACTER_ICONS.normal
  const currentX = ratio * VIEW_WIDTH

  return (
    <svg viewBox={`0 0 ${VIEW_WIDTH} ${VIEW_HEIGHT}`} role="img" aria-label={summaryText} className="h-6 w-full">
      <line
        x1={0}
        y1={ROAD_Y}
        x2={VIEW_WIDTH}
        y2={ROAD_Y}
        stroke={resolveAxisLineColor()}
        strokeWidth={1.5}
      />
      <line
        x1={0}
        y1={ROAD_Y}
        x2={currentX}
        y2={ROAD_Y}
        stroke={cycleSeriesColor(0)}
        strokeWidth={1.5}
      />
      <image
        href={currentIcon}
        x={currentX - ICON_SIZE / 2}
        y={ROAD_Y - ICON_SIZE}
        width={ICON_SIZE}
        height={ICON_SIZE}
        aria-hidden="true"
      />
      <image
        href={isAchieved ? CHARACTER_ICONS.achieved : CHARACTER_ICONS.normal}
        x={VIEW_WIDTH - ICON_SIZE}
        y={ROAD_Y - ICON_SIZE}
        width={ICON_SIZE}
        height={ICON_SIZE}
        opacity={isAchieved ? 1 : 0.35}
        aria-hidden="true"
      />
    </svg>
  )
}
