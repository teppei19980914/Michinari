import { t } from '../../locales/t'

/** 習得の種類別内訳（「用語◯/◯語・場面◯/◯件」、開発Todo_単語帳_v1.0 要件F F-U9）の表示。
 * 単語帳詳細（VocabDeckHeader）・単語帳一覧（VocabDeckListTab）・道のりマップ
 * （VocabMasteryRoadmapSection）の3箇所で同一の表示を使うため共通化する
 * （CODING_RULES.md①DRYの原則、dry-reviewerレビューで検出）。 */
export function VocabMasteryBreakdownLine({
  termMastered,
  termTotal,
  situationMastered,
  situationTotal,
}: {
  termMastered: number
  termTotal: number
  situationMastered: number
  situationTotal: number
}) {
  return (
    <p className="text-xs text-text-faint">
      {t('vocab.deckDetail.masteredCountBreakdown', {
        termMastered,
        termTotal,
        situationMastered,
        situationTotal,
      })}
    </p>
  )
}
