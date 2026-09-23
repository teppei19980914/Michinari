import { CHARACTER_ICONS, type CharacterIconKey } from '../../constants/characterIcons'

export type ScheduleStatus = 'delayed' | 'onTrack' | 'ahead'

const SCHEDULE_STATUS_ICON: Record<ScheduleStatus, CharacterIconKey> = {
  delayed: 'scheduleDelayed',
  onTrack: 'scheduleOnTrack',
  ahead: 'scheduleAhead',
}

/**
 * 完了予測日と締切の乖離日数（`forecast_deviation_days`等）から進捗状態を判定する
 * （仕様書v1.1 13.4、符号のみで3分岐）。
 *
 * 完了予測は資格試験（category=EXAM）目標にのみ存在する値（R-71・R-74）のため、呼び出し側は
 * 読書・仕事目標にこの関数を使わないこと（13.4「資格試験目標にのみ表示し、読書・仕事目標には
 * 表示しない」）。
 */
export function resolveScheduleStatus(overrunDays: number | null): ScheduleStatus | null {
  if (overrunDays === null) {
    return null
  }
  if (overrunDays > 0) {
    return 'delayed'
  }
  if (overrunDays < 0) {
    return 'ahead'
  }
  return 'onTrack'
}

/** UI-02/03/04のうち、進捗状態に対応するアイコンの画像URLを返す（値がない場合はnull）。 */
export function resolveScheduleStatusIcon(overrunDays: number | null): string | null {
  const status = resolveScheduleStatus(overrunDays)
  return status ? CHARACTER_ICONS[SCHEDULE_STATUS_ICON[status]] : null
}
