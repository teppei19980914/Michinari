/**
 * 気分スタンプ（ひとこと記録モード、開発Todo「ひとこと記録」v1.0 決定事項D1・Q6）の
 * 定義。5段階固定、絵文字＋ラベル併記（Q6）。表示文言はロケールへ外部化し
 * （CLAUDE.mdゼロハードコーディング）、絵文字自体は言語を問わず同じ見た目のため
 * ここへ直接置く（ロケールキーとの対応はMoodStampPicker.tsx側で解決する）。
 */

export const MOOD_VALUES = [1, 2, 3, 4, 5] as const

export type MoodValue = (typeof MOOD_VALUES)[number]

export function isMoodValue(value: number): value is MoodValue {
  return (MOOD_VALUES as readonly number[]).includes(value)
}
