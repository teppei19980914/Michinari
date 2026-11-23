/** 長文の折りたたみ（開発Todo_単語帳_v1.0 要件F F-U10）の表示判定ロジック。
 * DOMでの実測（ResizeObserver等）は使わず、改行数・文字数からの簡易な見積もりで
 * 「おそらく3行を超える」かどうかを判定する（`ExpandableText`の表示用、CODING_RULES.md
 * 「複雑度」を避けるため、過剰な精度を狙わない）。
 */

const MAX_LINES = 3
const CHARS_PER_LINE_ESTIMATE = 40

/** 折りたたみ・「続きを読む」ボタンの表示が必要かどうかを判定する。 */
export function isTextTruncatable(text: string): boolean {
  const lineCount = text.split('\n').length
  if (lineCount > MAX_LINES) return true
  return text.length > MAX_LINES * CHARS_PER_LINE_ESTIMATE
}
