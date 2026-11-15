import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { t } from '../../locales/t'
import { ROUTES } from '../../constants/routes'
import { Card } from '../../components/Card'
import { Button } from '../../components/Button'
import { Input } from '../../components/Input'
import { Textarea } from '../../components/Textarea'
import { useToast } from '../../components/toastContext'
import { apiErrorMessage } from '../../api/client'
import {
  createVocabDeck,
  deleteVocabDeck,
  getVocabDecks,
  reorderVocabDecks,
  type VocabDeck,
} from '../../api/vocab'
import { QUERY_KEYS } from '../../constants/queryKeys'
import { swapByOffset } from './vocabDeckOrder'

function CreateVocabDeckForm({ goalId, onDone }: { goalId: number; onDone: () => void }) {
  const queryClient = useQueryClient()
  const { showApiError } = useToast()
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')

  const mutation = useMutation({
    mutationFn: () => createVocabDeck(goalId, { name, description: description || null }),
    meta: { overlay: 'saving' },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.vocabDecks(goalId) })
      onDone()
    },
    onError: showApiError,
  })

  return (
    <form
      className="flex flex-col gap-3"
      onSubmit={(event) => {
        event.preventDefault()
        mutation.mutate()
      }}
    >
      <label className="flex flex-col gap-1 text-sm text-text-secondary">
        {t('vocab.deckList.nameLabel')}
        <Input value={name} onChange={(e) => setName(e.target.value)} required />
      </label>
      <label className="flex flex-col gap-1 text-sm text-text-secondary">
        {t('vocab.deckList.descriptionLabel')}
        <Textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={2} />
      </label>
      <div className="flex justify-end gap-2">
        <Button type="button" variant="secondary" onClick={onDone}>
          {t('common.action.cancel')}
        </Button>
        <Button type="submit" disabled={mutation.isPending}>
          {t('common.action.save')}
        </Button>
      </div>
    </form>
  )
}

/** 目標詳細「単語帳」タブ（開発Todo_単語帳_v1.0 要件A）。資格試験の目標のみに表示する
 * （§0 U1）。目標の状態に関わらず常に編集可能なため、他タブと異なりreadOnlyを受け取らない。 */
export function VocabDeckListTab({ goalId }: { goalId: number }) {
  const queryClient = useQueryClient()
  const { showApiError } = useToast()
  const [createOpen, setCreateOpen] = useState(false)

  const decksQuery = useQuery({
    queryKey: QUERY_KEYS.vocabDecks(goalId),
    queryFn: () => getVocabDecks(goalId),
  })

  const reorderMutation = useMutation({
    mutationFn: (orderedDeckIds: number[]) => reorderVocabDecks(goalId, orderedDeckIds),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: QUERY_KEYS.vocabDecks(goalId) }),
    onError: showApiError,
  })
  const deleteMutation = useMutation({
    mutationFn: (deckId: number) => deleteVocabDeck(deckId),
    meta: { overlay: 'deleting' },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: QUERY_KEYS.vocabDecks(goalId) }),
    onError: showApiError,
  })

  if (decksQuery.isLoading) {
    return <p className="text-sm text-text-faint">{t('common.loading')}</p>
  }
  if (decksQuery.isError || !decksQuery.data) {
    return <p className="text-sm text-danger-text">{apiErrorMessage(decksQuery.error)}</p>
  }

  const decks = decksQuery.data
  const move = (index: number, offset: number) => {
    const ordered = swapByOffset(decks.map((deck: VocabDeck) => deck.id), index, offset)
    reorderMutation.mutate(ordered)
  }

  return (
    <div className="flex flex-col gap-3">
      {decks.length === 0 && !createOpen && (
        <p className="text-sm text-text-faint">{t('vocab.deckList.empty')}</p>
      )}

      {decks.map((deck: VocabDeck, index: number) => (
        <Card key={deck.id} className="flex items-center justify-between gap-3">
          <Link to={ROUTES.vocabDeck(deck.id)} className="flex-1">
            <p className="text-sm font-medium text-text-primary">{deck.name}</p>
            <p className="text-sm text-text-faint">
              {t('vocab.deckList.cardCount', { count: deck.card_count })}
              {!deck.use_in_ai && ` · ${t('vocab.deckList.useInAiOffBadge')}`}
            </p>
          </Link>
          <div className="flex gap-1">
            <Button
              variant="secondary"
              disabled={index === 0}
              onClick={() => move(index, -1)}
              aria-label={t('vocab.deckList.moveUp')}
            >
              ↑
            </Button>
            <Button
              variant="secondary"
              disabled={index === decks.length - 1}
              onClick={() => move(index, 1)}
              aria-label={t('vocab.deckList.moveDown')}
            >
              ↓
            </Button>
            <Button
              variant="secondary"
              onClick={() => {
                if (window.confirm(t('common.confirmDelete'))) {
                  deleteMutation.mutate(deck.id)
                }
              }}
            >
              {t('common.action.delete')}
            </Button>
          </div>
        </Card>
      ))}

      {createOpen ? (
        <Card>
          <CreateVocabDeckForm goalId={goalId} onDone={() => setCreateOpen(false)} />
        </Card>
      ) : (
        <Button variant="secondary" onClick={() => setCreateOpen(true)}>
          {t('vocab.deckList.addTitle')}
        </Button>
      )}
    </div>
  )
}
