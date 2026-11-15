/** 単語帳の出題セッションの進行・結果集計（純粋関数、CODING_RULES.md「フロントの分岐は
 * .tsへ切り出す」）。進行（isLastQuestion/nextIndex）は復習クイズと共通のため
 * `utils/sessionProgress.ts`から再利用し、結果集計は単語帳固有のためここに残す。 */
export { isLastQuestion, nextIndex } from '../../utils/sessionProgress'

export type VocabAnswerRecord = {
  cardId: number
  term: string
  isCorrect: boolean
}

export type VocabSessionSummary = {
  correctCount: number
  totalCount: number
  accuracyPercent: number | null
  wrongCards: { cardId: number; term: string }[]
}

export function buildSessionSummary(results: VocabAnswerRecord[]): VocabSessionSummary {
  const correctCount = results.filter((result) => result.isCorrect).length
  const totalCount = results.length
  const wrongCards = results
    .filter((result) => !result.isCorrect)
    .map(({ cardId, term }) => ({ cardId, term }))
  return {
    correctCount,
    totalCount,
    accuracyPercent: totalCount === 0 ? null : (correctCount / totalCount) * 100,
    wrongCards,
  }
}
