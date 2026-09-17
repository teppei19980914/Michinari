import { useQuery, type UseQueryResult } from '@tanstack/react-query'
import { getCalendar, type DayType } from '../../api/calendar'
import { QUERY_KEYS } from '../../constants/queryKeys'

/** 対象日1日分の日種別を取得する（ゼロ記録確定後のメッセージ出し分けに使う、仕様書6.5改）。
 * 既存の GET /calendar を単日レンジで呼ぶ（専用APIは設けない）。キャッシュキーは
 * calendarRange と揃え、カレンダー更新時の無効化が自然に及ぶようにする。 */
export function useDayType(targetDate: string): UseQueryResult<DayType | undefined> {
  return useQuery({
    queryKey: QUERY_KEYS.calendarRange(targetDate, targetDate),
    queryFn: () => getCalendar(targetDate, targetDate),
    select: (days) => days[0]?.day_type,
  })
}
