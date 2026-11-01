import { t } from '../../locales/t'
import {
  cycleSeriesColor,
  resolveGridLineColor,
  resolvePlanLineColor,
  THRESHOLD_LINE_COLOR,
} from '../analytics/chartColors'
import { resolveByGoalCategory } from './goalCategoryVariant'
import type { GoalCategory } from '../../api/goals'

type LegendKind = 'actualLine' | 'plannedLine' | 'feedbackMark' | 'bufferMark' | 'replanMark' | 'footprint'

const LEGEND_ITEMS: Record<LegendKind, { labelKey: string }> = {
  actualLine: { labelKey: 'goals.roadmap.actualLineLabel' },
  plannedLine: { labelKey: 'goals.roadmap.plannedLineLabel' },
  feedbackMark: { labelKey: 'goals.roadmap.feedbackMarkLabel' },
  bufferMark: { labelKey: 'goals.roadmap.bufferMarkLabel' },
  replanMark: { labelKey: 'goals.roadmap.replanMarkLabel' },
  footprint: { labelKey: 'goals.roadmap.footprintLabel' },
}

type RoadmapLegendProps = { category: GoalCategory }

function LegendSwatch({ kind }: { kind: LegendKind }) {
  if (kind === 'actualLine') {
    return (
      <svg viewBox="0 0 16 10" className="h-2.5 w-4 shrink-0" aria-hidden="true">
        <line x1={0} y1={5} x2={16} y2={5} stroke={cycleSeriesColor(0)} strokeWidth={2} />
      </svg>
    )
  }
  if (kind === 'plannedLine') {
    return (
      <svg viewBox="0 0 16 10" className="h-2.5 w-4 shrink-0" aria-hidden="true">
        <line
          x1={0}
          y1={5}
          x2={16}
          y2={5}
          stroke={resolvePlanLineColor()}
          strokeWidth={2}
          strokeDasharray="3 2"
        />
      </svg>
    )
  }
  if (kind === 'replanMark') {
    return (
      <svg viewBox="0 0 16 10" className="h-2.5 w-4 shrink-0" aria-hidden="true">
        <line
          x1={8}
          y1={0}
          x2={8}
          y2={10}
          stroke={THRESHOLD_LINE_COLOR}
          strokeWidth={2}
          strokeDasharray="2 1.5"
        />
      </svg>
    )
  }
  if (kind === 'bufferMark') {
    return (
      <svg viewBox="0 0 16 10" className="h-2.5 w-4 shrink-0" aria-hidden="true">
        <line x1={8} y1={1} x2={8} y2={9} stroke={resolveGridLineColor()} strokeWidth={2} />
      </svg>
    )
  }
  if (kind === 'footprint') {
    return (
      <svg viewBox="0 0 16 10" className="h-2.5 w-4 shrink-0" aria-hidden="true">
        <circle cx={8} cy={5} r={3} fill={cycleSeriesColor(0)} opacity={0.4} />
      </svg>
    )
  }
  return (
    <svg viewBox="0 0 16 10" className="h-2.5 w-4 shrink-0" aria-hidden="true">
      <circle cx={8} cy={5} r={3} fill={cycleSeriesColor(2)} />
    </svg>
  )
}

/**
 * 道のりマップ詳細版（`GoalRoadmapTab`）の凡例。線の色・点線・マークが何を示すかを
 * 文字で補う（図だけでは「何が何を表しているか分かりづらい」という利用者フィードバックへの
 * 対応）。種別ごとに実在する要素のみ並べる（§0・25章の種別別の算出に合わせる）。
 */
export function RoadmapLegend({ category }: RoadmapLegendProps) {
  const kinds = resolveByGoalCategory<LegendKind[]>(category, {
    EXAM: ['actualLine', 'plannedLine', 'feedbackMark', 'bufferMark', 'replanMark'],
    READING: ['actualLine', 'plannedLine', 'feedbackMark', 'bufferMark', 'footprint'],
    WORK: ['feedbackMark', 'footprint'],
  })

  return (
    <ul className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-text-faint">
      {kinds.map((kind) => (
        <li key={kind} className="flex items-center gap-1.5">
          <LegendSwatch kind={kind} />
          <span>{t(LEGEND_ITEMS[kind].labelKey)}</span>
        </li>
      ))}
    </ul>
  )
}
