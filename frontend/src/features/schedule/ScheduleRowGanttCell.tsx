import { ScheduleGanttProposedBand } from './ScheduleGanttProposedBand'
import { ScheduleGanttRow } from './ScheduleGanttRow'
import type { ScheduleDraftItem } from './scheduleDraftTypes'

/**
 * 1行のガント部分（既存のバー`ScheduleGanttRow`＋未判断の修正案の点線重ね
 * `ScheduleGanttProposedBand`、単位5・D-57）。`ScheduleDataRow`を1関数100行以内に
 * 収めるための分離（CODING_RULES.md「保守性（複雑度）」）。
 */
export function ScheduleRowGanttCell({
  item,
  rangeStartIso,
  dayWidthRem,
  ganttWidthRem,
  today,
  proposedBand,
}: {
  item: ScheduleDraftItem
  rangeStartIso: string
  dayWidthRem: number
  ganttWidthRem: number
  today: string
  proposedBand: { start: string; end: string } | null
}) {
  return (
    <div className="relative shrink-0 bg-surface" style={{ width: `${ganttWidthRem}rem` }}>
      <ScheduleGanttRow
        title={item.title}
        item={{
          status: item.status,
          planned_start_date: item.plannedStartDate,
          planned_end_date: item.plannedEndDate,
          actual_start_date: item.actualStartDate,
          actual_end_date: item.actualEndDate,
        }}
        rangeStartIso={rangeStartIso}
        dayWidthRem={dayWidthRem}
        today={today}
      />
      {proposedBand && (
        <ScheduleGanttProposedBand
          rangeStartIso={rangeStartIso}
          dayWidthRem={dayWidthRem}
          plannedStartDate={proposedBand.start}
          plannedEndDate={proposedBand.end}
        />
      )}
    </div>
  )
}
