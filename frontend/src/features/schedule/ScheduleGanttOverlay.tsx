import type { DayTypeRun } from './scheduleGanttGeometry'

/**
 * 土日祝の網掛け・本日線（3.4「グリッド全体に1回だけ重ねて描く」）。日ごとのDOM要素では
 * なく、連続する同種の日をまとめた矩形（`computeDayTypeRuns`）を描く。装飾要素のため
 * `aria-hidden`とする。親要素（ガント領域全体）に`position: relative`を前提とする。
 */
export function ScheduleGanttOverlay({
  dayTypeRuns,
  todayLineLeftRem,
}: {
  dayTypeRuns: DayTypeRun[]
  todayLineLeftRem: number
}) {
  return (
    <div aria-hidden="true" className="pointer-events-none absolute inset-0">
      {dayTypeRuns.map((run) => (
        <div
          key={`${run.type}-${run.leftRem}`}
          data-testid={`day-type-run-${run.type}`}
          className={
            run.type === 'saturday'
              ? 'absolute inset-y-0 bg-schedule-saturday-bg'
              : 'absolute inset-y-0 bg-schedule-holiday-bg'
          }
          style={{ left: `${run.leftRem}rem`, width: `${run.widthRem}rem` }}
        />
      ))}
      <div
        data-testid="today-line"
        className="absolute inset-y-0 w-px bg-schedule-today-line"
        style={{ left: `${todayLineLeftRem}rem` }}
      />
    </div>
  )
}
