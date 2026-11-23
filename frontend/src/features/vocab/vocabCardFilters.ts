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
  'UNMASTERED',
] as const

export type VocabCardFilterKey = (typeof VOCAB_CARD_FILTER_KEYS)[number]

/** 「カードの種類」の絞り込みキー（開発Todo_単語帳_v1.0 要件F F-U3）。カード一覧・
 * 一括登録・出題セッション開始フォームで共通して使う（CODING_RULES.md①DRYの原則）。
 * 表示文言は`vocab.cardType.*`（`t()`経由）で解決する。 */
export const VOCAB_CARD_TYPE_KEYS = ['ALL', 'TERM', 'SITUATION'] as const

export type VocabCardTypeKey = (typeof VOCAB_CARD_TYPE_KEYS)[number]
