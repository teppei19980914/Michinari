/** カード一覧・出題セッション開始フォームの両方で使う絞り込みキー（CODING_RULES.md
 * ①DRYの原則。`VocabCardList.tsx`・`VocabQuizSetupForm.tsx`で同一の配列を直書きしていた
 * のを集約、dry-reviewerレビューで検出、2026-11-15）。表示文言は
 * `vocab.deckDetail.filterOptions.*`（`t()`経由）で解決する。 */
export const VOCAB_CARD_FILTER_KEYS = [
  'ALL',
  'CHECKED',
  'EVER_WRONG',
  'CONSECUTIVE_WRONG',
  'WEAK',
  'UNANSWERED',
] as const

export type VocabCardFilterKey = (typeof VOCAB_CARD_FILTER_KEYS)[number]
