import { t } from '../../locales/t'
import { formatDateTick } from '../analytics/formatPeriod'
import { Tooltip } from '../../components/Tooltip'
import type { ScheduleItemStatus } from '../../api/schedule'
import {
  computeActualBandRange,
  computeBandRem,
  type ScheduleGanttItemInput,
} from './scheduleGanttGeometry'
import { computeDelayInfo } from './scheduleDelay'

//: 実績帯の色（D-18：進行中はアクセント色、完了は成功を表す緑、中止はグレー）。
//: 未着手は実績帯を持たない（computeActualBandRangeが常にnullを返すため使われない）。
const ACTUAL_BAND_COLOR_CLASS: Record<ScheduleItemStatus, string> = {
  NOT_STARTED: '',
  IN_PROGRESS: 'bg-accent',
  DONE: 'bg-success',
  CANCELLED: 'bg-border-strong',
}

function buildTooltipLabel(
  title: string,
  item: ScheduleGanttItemInput,
  actualRange: { startIso: string; endIso: string } | null,
  delayInfo: { kind: 'END_DELAY' | 'START_DELAY'; days: number } | null,
): string {
  const lines = [
    title,
    t('schedule.gantt.tooltip.planned', {
      start: formatDateTick(item.planned_start_date),
      end: formatDateTick(item.planned_end_date),
    }),
    actualRange
      ? t('schedule.gantt.tooltip.actual', {
          start: formatDateTick(actualRange.startIso),
          end: formatDateTick(actualRange.endIso),
        })
      : t('schedule.gantt.tooltip.noActual'),
  ]
  if (delayInfo !== null) {
    const key =
      delayInfo.kind === 'START_DELAY' ? 'schedule.gantt.notStartedDelayDays' : 'schedule.gantt.delayDays'
    lines.push(t(key, { days: delayInfo.days, count: delayInfo.days }))
  }
  return lines.join(' / ')
}

/**
 * 1行分のガント（予定帯・実績帯・遅れの印、D-17・D-18・D-27）。帯にマウスを当てると
 * 作業項目・予定期間・実績期間・状況・遅れ日数をTooltipで表示する。
 */
export function ScheduleGanttRow({
  title,
  item,
  rangeStartIso,
  dayWidthRem,
  today,
}: {
  title: string
  item: ScheduleGanttItemInput
  rangeStartIso: string
  dayWidthRem: number
  today: string
}) {
  const plannedBand = computeBandRem(
    rangeStartIso,
    item.planned_start_date,
    item.planned_end_date,
    dayWidthRem,
  )
  const actualRange = computeActualBandRange(item, today)
  const actualBand = actualRange
    ? computeBandRem(rangeStartIso, actualRange.startIso, actualRange.endIso, dayWidthRem)
    : null
  const delayInfo = computeDelayInfo(item, today)
  const delayMarkLeftRem = (actualBand ?? plannedBand).leftRem + (actualBand ?? plannedBand).widthRem

  return (
    <Tooltip
      label={buildTooltipLabel(title, item, actualRange, delayInfo)}
      position="below"
      // Tooltip本体の既定クラスに`relative`が含まれるため、`absolute`を追加指定しても
      // CSSの詳細度が同じ`relative`に負けて無効化される（独立レビュー指摘、コンパイル済み
      // CSSで確認済み）。親セル（`ScheduleDataRow`のガント列、flexでstretchされ高さが
      // 確定済み）に対して`h-full w-full`で埋める指定のみにし、`absolute`は使わない。
      wrapperClassName="h-full w-full"
    >
      <div data-testid="schedule-gantt-row" className="relative h-full w-full">
        <div
          data-testid="planned-band"
          className="absolute top-1 h-2 rounded bg-schedule-planned-bg"
          style={{ left: `${plannedBand.leftRem}rem`, width: `${plannedBand.widthRem}rem` }}
        />
        {actualBand && (
          <div
            data-testid="actual-band"
            className={`absolute top-4 h-2 rounded ${ACTUAL_BAND_COLOR_CLASS[item.status]}`}
            style={{ left: `${actualBand.leftRem}rem`, width: `${actualBand.widthRem}rem` }}
          />
        )}
        {delayInfo !== null && (
          <div
            data-testid="delay-mark"
            className="absolute top-0 h-full w-0.5 bg-schedule-delay-mark"
            style={{ left: `${delayMarkLeftRem}rem` }}
          />
        )}
      </div>
    </Tooltip>
  )
}
