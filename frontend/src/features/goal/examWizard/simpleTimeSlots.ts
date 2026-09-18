/** ウィザードの簡易時間設定（平日/休日それぞれ何時間）から、時間スロットの開始・終了
 * 時刻を算出する（仕様書「簡易時間設定からスロットへの変換」）。
 *
 * 開始時刻は仮の値とする（平日20:00、休日09:00。仕様書の例「平日2時間→20:00〜22:00」に
 * 合わせた）。TIME型は24:00を表現できないため、24:00をまたぐ入力は23:59に切り詰める
 * （`clamped`で呼び出し側に伝え、「時刻は目安です」に加えて上限に達した旨を示せるように
 * する）。 */

export const WEEKDAY_START_HOUR = 20
export const WEEKEND_START_HOUR = 9
const MAX_END_MINUTES = 24 * 60 - 1

function formatTime(totalMinutes: number): string {
  const hour = Math.floor(totalMinutes / 60)
  const minute = totalMinutes % 60
  return `${String(hour).padStart(2, '0')}:${String(minute).padStart(2, '0')}`
}

export type SimpleSlotTimes = {
  startTime: string
  endTime: string
  clamped: boolean
}

function resolveSlotTimes(startHour: number, hours: number): SimpleSlotTimes {
  const startMinutes = startHour * 60
  const rawEndMinutes = startMinutes + hours * 60
  const endMinutes = Math.min(rawEndMinutes, MAX_END_MINUTES)
  return {
    startTime: formatTime(startMinutes),
    endTime: formatTime(endMinutes),
    clamped: rawEndMinutes > MAX_END_MINUTES,
  }
}

export function resolveWeekdaySlotTimes(hours: number): SimpleSlotTimes {
  return resolveSlotTimes(WEEKDAY_START_HOUR, hours)
}

export function resolveWeekendSlotTimes(hours: number): SimpleSlotTimes {
  return resolveSlotTimes(WEEKEND_START_HOUR, hours)
}
