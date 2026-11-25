import { computeBandRem } from './scheduleGanttGeometry'

/**
 * 未判断の修正案（CHANGE行）の予定帯を、ガントへ点線で重ねて表示する
 * （開発Todo_スケジュール・ガントチャート_v1.1 D-57・13.8、単位5）。
 * 日付を手で修正した場合は修正後の値で表示する（呼び出し側が`plannedStartDate`・
 * `plannedEndDate`に編集後の値を渡す）。
 */
export function ScheduleGanttProposedBand({
  rangeStartIso,
  dayWidthRem,
  plannedStartDate,
  plannedEndDate,
}: {
  rangeStartIso: string
  dayWidthRem: number
  plannedStartDate: string
  plannedEndDate: string
}) {
  const band = computeBandRem(rangeStartIso, plannedStartDate, plannedEndDate, dayWidthRem)
  return (
    <div
      data-testid="proposed-band"
      className="absolute top-0.5 h-3 rounded border-2 border-dashed border-accent bg-transparent"
      style={{ left: `${band.leftRem}rem`, width: `${band.widthRem}rem` }}
    />
  )
}
