import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { t } from '../../locales/t'
import { apiErrorMessage } from '../../api/client'
import { getVocabDecks, generateVocabDeckQuiz, updateVocabDeck } from '../../api/vocab'
import { useToast } from '../../components/toastContext'
import { useAiConfigured } from '../../hooks/useAiConfigured'
import { QUERY_KEYS } from '../../constants/queryKeys'
import { VocabCardList } from './VocabCardList'
import { VocabDeckAiSection } from './VocabDeckAiSection'
import { VocabImportExportPanel } from './VocabImportExportPanel'
import { VocabMasteryBreakdownLine } from './VocabMasteryBreakdownLine'

/** 目標詳細「単語帳」タブ（開発Todo_単語帳_出題導線改修_v1.0 U1・U7・U10）。単語帳
 * （デッキ）はユーザーに見せず、1目標につき常に1件存在する前提で、その唯一のデッキに
 * 対する単語のCRUD・AI設定（今日の復習での利用・問題作成）・インポート/エクスポートを
 * まとめる。デッキ自体の作成・名前編集・削除・一覧表示（旧VocabDeckListTab）は廃止した。 */
export function VocabDeckWordsTab({ goalId }: { goalId: number }) {
  const queryClient = useQueryClient()
  const { showApiError, showToast } = useToast()
  const aiConfigured = useAiConfigured()

  const decksQuery = useQuery({
    queryKey: QUERY_KEYS.vocabDecks(goalId),
    queryFn: () => getVocabDecks(goalId),
  })

  const deck = decksQuery.data?.[0]

  const updateMutation = useMutation({
    mutationFn: (payload: { use_in_ai: boolean }) => updateVocabDeck(deck!.id, payload),
    meta: { overlay: 'saving' },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: QUERY_KEYS.vocabDecks(goalId) }),
    onError: showApiError,
  })
  const generateQuizMutation = useMutation({
    mutationFn: () => generateVocabDeckQuiz(deck!.id),
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

  if (decksQuery.isLoading) {
    return <p className="text-sm text-text-faint">{t('common.loading')}</p>
  }
  if (decksQuery.isError || !deck) {
    return <p className="text-sm text-danger-text">{apiErrorMessage(decksQuery.error)}</p>
  }

  return (
    <div className="flex flex-col gap-3">
      <p className="text-sm text-text-secondary">
        {t('vocab.deckDetail.masteredCount', {
          mastered: deck.mastered_card_count,
          total: deck.card_count,
        })}
      </p>
      <VocabMasteryBreakdownLine
        termMastered={deck.term_mastered_card_count}
        termTotal={deck.term_card_count}
        situationMastered={deck.situation_mastered_card_count}
        situationTotal={deck.situation_card_count}
      />

      <VocabDeckAiSection
        useInAi={deck.use_in_ai}
        onToggleUseInAi={(checked) => updateMutation.mutate({ use_in_ai: checked })}
        aiConfigured={aiConfigured}
        isGenerating={generateQuizMutation.isPending}
        onGenerateQuiz={() => generateQuizMutation.mutate()}
      />

      <VocabImportExportPanel deckId={deck.id} deckName={deck.name} />

      <VocabCardList deckId={deck.id} />
    </div>
  )
}
