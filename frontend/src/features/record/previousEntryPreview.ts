/** 「前回はこう書いていました」ヒント表示用のプレビュー長（仕様書6.5改、記録画面改善
 * タスク2026-09-17「前回の記録の冒頭（100文字程度）」）。 */
const PREVIEW_LENGTH = 100

export type PreviousEntryPreview = {
  preview: string
  isTruncated: boolean
}

/** 前回の記録本文からプレビュー（冒頭100文字程度）を切り出す。 */
export function buildPreviousEntryPreview(body: string): PreviousEntryPreview {
  if (body.length <= PREVIEW_LENGTH) {
    return { preview: body, isTruncated: false }
  }
  return { preview: body.slice(0, PREVIEW_LENGTH), isTruncated: true }
}
