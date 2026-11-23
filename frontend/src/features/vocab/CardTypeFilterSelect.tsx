import { t } from '../../locales/t'
import { VOCAB_CARD_TYPE_KEYS, type VocabCardTypeKey } from './vocabCardFilters'

/** 「カードの種類」絞り込み（ALL/TERM/SITUATION）の選択欄。カード一覧
 * （VocabCardList）・問題集の開始フォーム（VocabQuizSetupForm）の両方で使う
 * （開発Todo_単語帳_v1.0 要件F F-U3、CODING_RULES.md①DRYの原則、dry-reviewerレビューで
 * 検出）。ALLを含まない一括登録・書き出し専用の選択欄は`VocabImportExportPanel`内の
 * `CardTypeSelect`（別コンポーネント）が担う。 */
export function CardTypeFilterSelect({
  label,
  value,
  onChange,
}: {
  label: string
  value: VocabCardTypeKey
  onChange: (value: VocabCardTypeKey) => void
}) {
  return (
    <label className="flex flex-col gap-1 text-sm text-text-secondary">
      {label}
      <select
        className="rounded-md border border-border-strong px-3 py-2 text-sm"
        value={value}
        onChange={(e) => onChange(e.target.value as VocabCardTypeKey)}
      >
        {VOCAB_CARD_TYPE_KEYS.map((key) => (
          <option key={key} value={key}>
            {t(`vocab.deckDetail.cardTypeOptions.${key}`)}
          </option>
        ))}
      </select>
    </label>
  )
}
