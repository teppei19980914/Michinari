import { formatPercent } from '../../utils/format'

/** 正答率をパーセント文字列へ整形する純粋関数（分母0件は「-」、CODING_RULES.mdテスト容易性）。
 * 百分率表示そのものは既存の`formatPercent`（CLAUDE.md DRYの原則）を使う。 */
export function formatAccuracyPercent(correctCount: number, answerCount: number): string {
  if (answerCount === 0) {
    return '-'
  }
  return formatPercent(correctCount / answerCount)
}
