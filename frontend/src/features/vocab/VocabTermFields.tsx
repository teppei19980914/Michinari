import { t } from '../../locales/t'
import { Input } from '../../components/Input'
import { Textarea } from '../../components/Textarea'
import type { VocabDeck } from '../../api/vocab'

export type VocabTermFieldsValue = {
  deckId: number
  term: string
  meaning: string
  aliases: string
}

/** 単語帳への追加先デッキ・用語・意味・別名の入力欄（開発Todo_単語帳_v1.0 要件D）。
 *
 * 用語提案の採用フォーム（`TodayVocabSuggestionsCard`）と、手動追加ボタンのフォーム
 * （`AddVocabTermButton`）の両方で同じ入力欄が必要なため、ここへ共通化する
 * （CODING_RULES.md「①DRYの原則」）。送信ボタン・キャンセルボタンは呼び出し側が持つ。
 */
export function VocabTermFields({
  decks,
  value,
  onChange,
}: {
  decks: VocabDeck[]
  value: VocabTermFieldsValue
  onChange: (value: VocabTermFieldsValue) => void
}) {
  return (
    <>
      <label className="flex flex-col gap-1 text-sm text-text-secondary">
        {t('vocab.suggestions.deckLabel')}
        <select
          className="rounded-md border border-border-strong px-3 py-2 text-sm"
          value={value.deckId}
          onChange={(e) => onChange({ ...value, deckId: Number(e.target.value) })}
        >
          {decks.map((deck) => (
            <option key={deck.id} value={deck.id}>
              {deck.name}
            </option>
          ))}
        </select>
      </label>
      <label className="flex flex-col gap-1 text-sm text-text-secondary">
        {t('vocab.suggestions.termLabel')}
        <Input
          value={value.term}
          onChange={(e) => onChange({ ...value, term: e.target.value })}
          required
        />
      </label>
      <label className="flex flex-col gap-1 text-sm text-text-secondary">
        {t('vocab.suggestions.meaningLabel')}
        <Textarea
          value={value.meaning}
          onChange={(e) => onChange({ ...value, meaning: e.target.value })}
          rows={2}
          required
        />
      </label>
      <label className="flex flex-col gap-1 text-sm text-text-secondary">
        {t('vocab.suggestions.aliasesLabel')}
        <Textarea
          value={value.aliases}
          onChange={(e) => onChange({ ...value, aliases: e.target.value })}
          rows={2}
          placeholder={t('vocab.deckDetail.aliasesHint')}
        />
      </label>
    </>
  )
}
