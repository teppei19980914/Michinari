import type { components } from '../../types/api.d.ts'

type DayType = components['schemas']['DayType']
type RecordState = components['schemas']['RecordState']

/**
 * カレンダーセルの背景色（日種別）を判定する（仕様書6.4 SC-05「背景色: 日種別
 * （計画日／バッファ日／除外日）」）。技術選定書4.5「カレンダーの色分けロジック」に該当し、
 * 組み合わせが多く目視確認では漏れるためテスト対象とする。
 */
const DAY_TYPE_BACKGROUND_CLASS: Record<DayType, string> = {
  PLAN: 'bg-white',
  BUFFER: 'bg-amber-50',
  OFF: 'bg-gray-100',
}

export function resolveCalendarCellBackgroundClass(dayType: DayType): string {
  return DAY_TYPE_BACKGROUND_CLASS[dayType]
}

/** カレンダーセルのマーカー（記録状態）に対応するロケールキーを判定する（仕様書6.4）。 */
const RECORD_STATE_MARKER_KEY: Record<'unreported' | RecordState, string> = {
  unreported: 'calendar.marker.unreported',
  PROGRESS_ONLY: 'calendar.marker.progressOnly',
  REPORTED: 'calendar.marker.reported',
}

export function resolveCalendarCellMarkerKey(recordState: RecordState | null): string {
  return RECORD_STATE_MARKER_KEY[recordState ?? 'unreported']
}
