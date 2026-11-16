import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { t } from '../../locales/t'
import { ROUTES } from '../../constants/routes'
import { Card } from '../../components/Card'
import { Button } from '../../components/Button'
import { Input } from '../../components/Input'
import { Textarea } from '../../components/Textarea'
import { AiUnconfiguredNotice } from '../../components/AiUnconfiguredNotice'
import { useToast } from '../../components/toastContext'
import {
  deleteVocabDeck,
  generateVocabDeckQuiz,
  updateVocabDeck,
  type VocabDeck,
} from '../../api/vocab'
import { useAiConfigured } from '../../hooks/useAiConfigured'
import { QUERY_KEYS } from '../../constants/queryKeys'

/** 単語帳詳細の見出し（名前・説明の編集、AI利用の切替、削除）。 */
export function VocabDeckHeader({ deck }: { deck: VocabDeck }) {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { showApiError, showToast } = useToast()
  const aiConfigured = useAiConfigured()
  const [editing, setEditing] = useState(false)
  const [name, setName] = useState(deck.name)
  const [description, setDescription] = useState(deck.description ?? '')

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
      {editing ? (
        <form
          className="flex flex-col gap-3"
          onSubmit={(event) => {
            event.preventDefault()
            updateMutation.mutate(
              { name, description: description || null },
              { onSuccess: () => setEditing(false) },
            )
          }}
        >
          <label className="flex flex-col gap-1 text-sm text-text-secondary">
            {t('vocab.deckList.nameLabel')}
            <Input value={name} onChange={(e) => setName(e.target.value)} required />
          </label>
          <label className="flex flex-col gap-1 text-sm text-text-secondary">
            {t('vocab.deckList.descriptionLabel')}
            <Textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={2}
            />
          </label>
          <div className="flex justify-end gap-2">
            <Button type="button" variant="secondary" onClick={() => setEditing(false)}>
              {t('common.action.cancel')}
            </Button>
            <Button type="submit" disabled={updateMutation.isPending}>
              {t('common.action.save')}
            </Button>
          </div>
        </form>
      ) : (
        <div className="flex items-start justify-between gap-3">
          <div>
            <h1 className="text-xl font-semibold text-text-primary">{deck.name}</h1>
            {deck.description && <p className="text-sm text-text-faint">{deck.description}</p>}
          </div>
          <Button variant="secondary" onClick={() => setEditing(true)}>
            {t('common.action.edit')}
          </Button>
        </div>
      )}

      <label className="flex items-center gap-2 text-sm text-text-secondary">
        <input
          type="checkbox"
          checked={deck.use_in_ai}
          onChange={(e) => updateMutation.mutate({ use_in_ai: e.target.checked })}
        />
        {t('vocab.deckDetail.useInAiLabel')}
      </label>
      <p className="text-xs text-text-faint">{t('vocab.deckDetail.useInAiDescription')}</p>

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
