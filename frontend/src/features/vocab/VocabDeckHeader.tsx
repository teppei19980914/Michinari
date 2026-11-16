import { useNavigate } from 'react-router-dom'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { t } from '../../locales/t'
import { ROUTES } from '../../constants/routes'
import { Card } from '../../components/Card'
import { Button } from '../../components/Button'
import { useToast } from '../../components/toastContext'
import {
  deleteVocabDeck,
  generateVocabDeckQuiz,
  updateVocabDeck,
  type VocabDeck,
} from '../../api/vocab'
import { useAiConfigured } from '../../hooks/useAiConfigured'
import { QUERY_KEYS } from '../../constants/queryKeys'
import { VocabDeckAiSection } from './VocabDeckAiSection'
import { VocabDeckNameSection } from './VocabDeckNameSection'

/** 単語帳詳細の見出し（名前・説明の編集、AI利用の切替、削除）。 */
export function VocabDeckHeader({ deck }: { deck: VocabDeck }) {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { showApiError, showToast } = useToast()
  const aiConfigured = useAiConfigured()

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: QUERY_KEYS.vocabDeck(deck.id) })
    queryClient.invalidateQueries({ queryKey: QUERY_KEYS.vocabDecks(deck.goal_id) })
  }

  const updateMutation = useMutation({
    mutationFn: (payload: { name?: string; description?: string | null; use_in_ai?: boolean }) =>
      updateVocabDeck(deck.id, payload),
    meta: { overlay: 'saving' },
    onSuccess: invalidate,
    onError: showApiError,
  })
  const deleteMutation = useMutation({
    mutationFn: () => deleteVocabDeck(deck.id),
    meta: { overlay: 'deleting' },
    onSuccess: () => navigate(ROUTES.goalDetail(deck.goal_id)),
    onError: showApiError,
  })
  const generateQuizMutation = useMutation({
    mutationFn: () => generateVocabDeckQuiz(deck.id),
    meta: { overlay: 'saving' },
    onSuccess: (result) => {
      showToast(
        result.created > 0
          ? t('vocab.deckDetail.quizGenerateSucceeded', { count: result.created })
          : t('vocab.deckDetail.quizGenerateSucceededNone'),
      )
    },
    onError: showApiError,
  })

  return (
    <Card className="flex flex-col gap-3">
      <VocabDeckNameSection
        deck={deck}
        onSave={(payload, options) => updateMutation.mutate(payload, options)}
        isSaving={updateMutation.isPending}
      />

      <VocabDeckAiSection
        useInAi={deck.use_in_ai}
        onToggleUseInAi={(checked) => updateMutation.mutate({ use_in_ai: checked })}
        aiConfigured={aiConfigured}
        isGenerating={generateQuizMutation.isPending}
        onGenerateQuiz={() => generateQuizMutation.mutate()}
      />

      <div>
        <Button
          variant="secondary"
          onClick={() => {
            if (window.confirm(t('common.confirmDelete'))) {
              deleteMutation.mutate()
            }
          }}
        >
          {t('common.action.delete')}
        </Button>
      </div>
    </Card>
  )
}
