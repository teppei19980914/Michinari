/** 単語帳詳細のAI連携セクション（VocabDeckHeader.tsxから切り出し。WorkEvaluationGenerateCard.tsxと
 * 同じ理由＝1関数100行の上限、CODING_RULES.md「保守性（複雑度）」）。
 * 「AIで使う」切替と「今日の復習の問題を作る」ボタン（開発Todo_単語帳_v1.0 要件B）。 */
import { t } from '../../locales/t'
import { Button } from '../../components/Button'
import { AiUnconfiguredNotice } from '../../components/AiUnconfiguredNotice'

export function VocabDeckAiSection({
  useInAi,
  onToggleUseInAi,
  aiConfigured,
  isGenerating,
  onGenerateQuiz,
}: {
  useInAi: boolean
  onToggleUseInAi: (checked: boolean) => void
  aiConfigured: boolean
  isGenerating: boolean
  onGenerateQuiz: () => void
}) {
  return (
    <>
      <label className="flex items-center gap-2 text-sm text-text-secondary">
        <input
          type="checkbox"
          checked={useInAi}
          onChange={(e) => onToggleUseInAi(e.target.checked)}
        />
        {t('vocab.deckDetail.useInAiLabel')}
      </label>
      <p className="text-xs text-text-faint">{t('vocab.deckDetail.useInAiDescription')}</p>

      {aiConfigured ? (
        <div>
          <Button variant="secondary" disabled={isGenerating} onClick={onGenerateQuiz}>
            {t('vocab.deckDetail.generateQuizButton')}
          </Button>
        </div>
      ) : (
        <AiUnconfiguredNotice />
      )}
    </>
  )
}
