import { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { getHolidayCoverage } from '../../api/resources'
import { QUERY_KEYS } from '../../constants/queryKeys'
import { computeDisplayRange } from './scheduleGanttGeometry'
import type { ScheduleDraftItem } from './scheduleDraftTypes'

/** 座標に影響する値（日付・状況）だけを連結した文字列。作業項目名等、無関係な入力の
 * たびに祝日クエリの表示期間を揺らさないための`useMemo`の依存値（パフォーマンスレビュー
 * 指摘。`items`は編集のたびに新しい配列になるため参照比較ではメモ化できない）。 */
function ganttRelevantSignature(items: ScheduleDraftItem[]): string {
  return items
    .map((item) =>
      [
        item.key,
        item.status,
        item.plannedStartDate,
        item.plannedEndDate,
        item.actualStartDate,
        item.actualEndDate,
      ].join('|'),
    )
    .join(';')
}

/**
 * スケジュールタブが使う祝日情報（D-45）。表示期間（全行の予定・実績と本日を含む日数）に
 * 対して`GET /holidays`を呼び、個別の祝日の集合と収録範囲（年）を返す。`ScheduleTab`から
 * 分離（複雑度対策）。
 */
export function useScheduleHolidays(items: ScheduleDraftItem[], today: string | null, enabled: boolean) {
  const ganttRelevantKey = ganttRelevantSignature(items)
  const range = useMemo(() => {
    const ganttItems = items.map((item) => ({
      status: item.status,
      planned_start_date: item.plannedStartDate,
      planned_end_date: item.plannedEndDate,
      actual_start_date: item.actualStartDate,
      actual_end_date: item.actualEndDate,
    }))
    return computeDisplayRange(ganttItems, today ?? '1970-01-01')
    // eslint-disable-next-line react-hooks/exhaustive-deps -- ganttRelevantKeyが実質的な依存値
  }, [ganttRelevantKey, today])

  const holidayQuery = useQuery({
    queryKey: QUERY_KEYS.holidayCoverage(range.startIso, range.endIso),
    queryFn: () => getHolidayCoverage(range.startIso, range.endIso),
    enabled,
  })

  const holidayData = holidayQuery.data?.holidays
  const holidayIsoDates = useMemo(
    () => new Set((holidayData ?? []).map((h) => h.holiday_date)),
    [holidayData],
  )

  return {
    holidayIsoDates,
    holidayYearFrom: holidayQuery.data?.year_from ?? null,
    holidayYearTo: holidayQuery.data?.year_to ?? null,
  }
}
