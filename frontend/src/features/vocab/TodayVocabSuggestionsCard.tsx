import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { t } from '../../locales/t'
import { Card } from '../../components/Card'
import { Button } from '../../components/Button'
import { useToast } from '../../components/toastContext'
import {
  acceptVocabTermSuggestion,
  dismissVocabTermSuggestion,
  getVocabDecks,
  getVocabTermSuggestions,
  type VocabDeck,
  type VocabTermSuggestion,
} from '../../api/vocab'
import { QUERY_KEYS } from '../../constants/queryKeys'
import { useAiConfigured } from '../../hooks/useAiConfigured'
import { VocabTermFields, type VocabTermFieldsValue } from './VocabTermFields'

function SuggestionRow({
  goalId,
  recordDate,
  suggestion,
  decks,
  defaultDeckId,
}: {
  goalId: number
  recordDate: string
  suggestion: VocabTermSuggestion
  decks: VocabDeck[]
  defaultDeckId: number
}) {
  const queryClient = useQueryClient()
  const { showApiError } = useToast()
  const [value, setValue] = useState<VocabTermFieldsValue>({
    deckId: defaultDeckId,
    term: suggestion.term,
    meaning: suggestion.source_sentence,
    aliases: '',
  })

  const invalidate = () =>
    queryClient.invalidateQueries({
      queryKey: QUERY_KEYS.vocabTermSuggestions(goalId, recordDate),
    })

  const acceptMutation = useMutation({
    mutationFn: () =>
      acceptVocabTermSuggestion(goalId, suggestion.id, {
        deck_id: value.deckId,
        term: value.term,
        meaning: value.meaning,
        aliases: value.aliases || null,
      }),
    meta: { overlay: 'saving' },
    onSuccess: invalidate,
    onError: showApiError,
  })
  const dismissMutation = useMutation({
    mutationFn: () => dismissVocabTermSuggestion(goalId, suggestion.id),
    onSuccess: invalidate,
    onError: showApiError,
  })

  return (
    <Card className="flex flex-col gap-3">
      <VocabTermFields decks={decks} value={value} onChange={setValue} />
      <div className="flex justify-end gap-2">
        <Button
          variant="secondary"
          disabled={dismissMutation.isPending}
          onClick={() => dismissMutation.mutate()}
        >
          {t('vocab.suggestions.dismissButton')}
        </Button>
        <Button disabled={acceptMutation.isPending} onClick={() => acceptMutation.mutate()}>
          {t('vocab.suggestions.addButton')}
        </Button>
      </div>
    </Card>
  )
}

/** 「今日の記録に出てきた用語」カード（開発Todo_単語帳_v1.0 要件D）。
 *
 * 日次報告の確定成功後のサマリ（ExamReportSection）・日次報告の閲覧画面
 * （DailyReportViewPage）の両方から、同じコンポーネントを使う。提案の生成（POST）は
 * 確定成功時に別途1回だけ呼ぶため（useDailyReportActions.ts、D-U4）、本コンポーネントは
 * 取得（GET）のみを行う。AI未設定・単語帳が1つも無い場合は何も呼ばない（単語帳が0件の
 * 場合のみ案内を出す）。提案が0件のときは何も表示しない（D-U4）。
 */
export function TodayVocabSuggestionsCard({
  goalId,
  recordDate,
}: {
  goalId: number
  recordDate: string
}) {
  const aiConfigured = useAiConfigured()
  const decksQuery = useQuery({
    queryKey: QUERY_KEYS.vocabDecks(goalId),
    queryFn: () => getVocabDecks(goalId),
    enabled: aiConfigured,
  })
  const decks = decksQuery.data ?? []
  const suggestionsQuery = useQuery({
    queryKey: QUERY_KEYS.vocabTermSuggestions(goalId, recordDate),
    queryFn: () => getVocabTermSuggestions(goalId, recordDate),
    enabled: aiConfigured && decks.length > 0,
  })

  if (!aiConfigured || decksQuery.isLoading) {
    return null
  }
  if (decks.length === 0) {
    return <p className="text-sm text-text-faint">{t('vocab.suggestions.noDeckNotice')}</p>
  }
  const suggestions = suggestionsQuery.data?.suggestions ?? []
  if (suggestions.length === 0) {
    return null
  }
  const defaultDeckId = suggestionsQuery.data?.default_deck_id ?? decks[0].id

  return (
    <section className="flex flex-col gap-3">
      <h2 className="font-medium text-text-primary">{t('vocab.suggestions.title')}</h2>
      {suggestions.map((suggestion) => (
        <SuggestionRow
          key={suggestion.id}
          goalId={goalId}
          recordDate={recordDate}
          suggestion={suggestion}
          decks={decks}
          defaultDeckId={defaultDeckId}
        />
      ))}
    </section>
  )
}
