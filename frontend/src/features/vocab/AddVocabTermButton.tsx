import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { t } from '../../locales/t'
import { Card } from '../../components/Card'
import { Button } from '../../components/Button'
import { useToast } from '../../components/toastContext'
import { createVocabCard, getVocabDecks, type VocabDeck } from '../../api/vocab'
import { QUERY_KEYS } from '../../constants/queryKeys'
import { VocabTermFields, type VocabTermFieldsValue } from './VocabTermFields'

/** 「単語帳に用語を追加」ボタン（開発Todo_単語帳_v1.0 要件D D-U6）。
 *
 * AIを使わない手段として、日次報告の閲覧画面に置く。カードの追加フォームを開き、
 * 用語・意味・別名を自由入力して単語帳へ追加できる（AI未設定でも使える）。単語帳が
 * 1つも無い場合は、ボタンの代わりに案内文のみを出す。
 */
export function AddVocabTermButton({ goalId }: { goalId: number }) {
  const [open, setOpen] = useState(false)
  const decksQuery = useQuery({
    queryKey: QUERY_KEYS.vocabDecks(goalId),
    queryFn: () => getVocabDecks(goalId),
  })
  const decks = decksQuery.data ?? []

  if (decksQuery.isLoading) {
    return null
  }
  if (decks.length === 0) {
    return <p className="text-sm text-text-faint">{t('vocab.suggestions.manualAddNoDeckNotice')}</p>
  }
  if (!open) {
    return (
      <Button variant="secondary" onClick={() => setOpen(true)}>
        {t('vocab.suggestions.manualAddButton')}
      </Button>
    )
  }
  return <AddVocabTermForm decks={decks} onDone={() => setOpen(false)} />
}

function AddVocabTermForm({ decks, onDone }: { decks: VocabDeck[]; onDone: () => void }) {
  const queryClient = useQueryClient()
  const { showApiError } = useToast()
  const [value, setValue] = useState<VocabTermFieldsValue>({
    deckId: decks[0].id,
    term: '',
    meaning: '',
    aliases: '',
  })

  const mutation = useMutation({
    mutationFn: () =>
      createVocabCard(value.deckId, {
        term: value.term,
        meaning: value.meaning,
        aliases: value.aliases || null,
      }),
    meta: { overlay: 'saving' },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.vocabCards(value.deckId) })
      onDone()
    },
    onError: showApiError,
  })

  return (
    <Card>
      <form
        className="flex flex-col gap-3"
        onSubmit={(event) => {
          event.preventDefault()
          mutation.mutate()
        }}
      >
        <VocabTermFields decks={decks} value={value} onChange={setValue} />
        <div className="flex justify-end gap-2">
          <Button type="button" variant="secondary" onClick={onDone}>
            {t('common.action.cancel')}
          </Button>
          <Button type="submit" disabled={mutation.isPending}>
            {t('common.action.save')}
          </Button>
        </div>
      </form>
    </Card>
  )
}
