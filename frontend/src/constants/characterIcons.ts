import uiNormal from '../assets/icons/ui-01-normal.png'
import uiScheduleDelayed from '../assets/icons/ui-02-schedule-delayed.png'
import uiScheduleOnTrack from '../assets/icons/ui-03-schedule-on-track.png'
import uiScheduleAhead from '../assets/icons/ui-04-schedule-ahead.png'
import uiRegistering from '../assets/icons/ui-05-registering.png'
import uiDeleting from '../assets/icons/ui-06-deleting.png'
import uiBuffer from '../assets/icons/ui-07-buffer.png'
import uiExam from '../assets/icons/ui-08-exam.png'
import uiReading from '../assets/icons/ui-09-reading.png'
import uiWork from '../assets/icons/ui-10-work.png'
import uiAchieved from '../assets/icons/ui-11-achieved.png'

/**
 * ミチナリのキャラクターアイコン11種（アイコンセット仕様書v1.0、仕様書v1.1 13.2）。
 * UI-01〜UI-11のIDをキーとし、対応する画像を一意に引けるようにする（DRY、重複importの回避）。
 */
export const CHARACTER_ICONS = {
  normal: uiNormal,
  scheduleDelayed: uiScheduleDelayed,
  scheduleOnTrack: uiScheduleOnTrack,
  scheduleAhead: uiScheduleAhead,
  registering: uiRegistering,
  deleting: uiDeleting,
  buffer: uiBuffer,
  exam: uiExam,
  reading: uiReading,
  work: uiWork,
  achieved: uiAchieved,
} as const

export type CharacterIconKey = keyof typeof CHARACTER_ICONS

/**
 * ブロッキングオーバーレイ（保存中・生成AI疎通中・削除中）の種別。
 * 生成AI疎通中はUI-05（登録中）を流用するため、`saving`と区別しない（仕様書v1.1 13.3）。
 */
export type OverlayKind = 'saving' | 'deleting'

export const OVERLAY_ICON: Record<OverlayKind, CharacterIconKey> = {
  saving: 'registering',
  deleting: 'deleting',
}
