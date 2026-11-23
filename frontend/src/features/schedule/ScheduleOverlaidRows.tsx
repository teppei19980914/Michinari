import type { ReactNode } from 'react'
import { ScheduleGanttOverlay } from './ScheduleGanttOverlay'
import type { DayTypeRun } from './scheduleGanttGeometry'

/**
 * 土日祝の網掛け・本日線（3.4「グリッド全体に1回だけ重ねて描く」）を、行の集まりの背後に
 * 重ねる共通ラッパー。固定行（sticky）側・スクロール側の両方に使う（独立レビュー指摘：
 * 固定行にオーバーレイが重なっていなかった不具合の修正）。オーバーレイ自体は両方の呼び出しで
 * 同じ`dayTypeRuns`・`todayLineLeftRem`（水平方向の位置のみ）を使い、高さは各呼び出し側の
 * 行の集まりの高さに自動で揃う（`absolute inset-0`）。
 */
export function ScheduleOverlaidRows({
  fixedAreaWidthRem,
  dayTypeRuns,
  todayLineLeftRem,
  children,
}: {
  fixedAreaWidthRem: number
  dayTypeRuns: DayTypeRun[]
  todayLineLeftRem: number
  children: ReactNode
}) {
  return (
    <div className="relative">
      <div className="absolute" style={{ left: `${fixedAreaWidthRem}rem`, top: 0, bottom: 0 }}>
        <ScheduleGanttOverlay dayTypeRuns={dayTypeRuns} todayLineLeftRem={todayLineLeftRem} />
      </div>
      {children}
    </div>
  )
}
