/** 単語帳詳細の名前・説明の表示・編集（VocabDeckHeader.tsxから切り出し。
 * VocabDeckAiSection.tsxと同じ理由＝1関数100行の上限、CODING_RULES.md「保守性（複雑度）」）。 */
import { useState } from 'react'
import { t } from '../../locales/t'
import { Button } from '../../components/Button'
import { Input } from '../../components/Input'
import { Textarea } from '../../components/Textarea'
import type { VocabDeck } from '../../api/vocab'

export function VocabDeckNameSection({
  deck,
  onSave,
  isSaving,
}: {
  deck: VocabDeck
  onSave: (
    payload: { name: string; description: string | null },
    options: { onSuccess: () => void },
  ) => void
  isSaving: boolean
}) {
  const [editing, setEditing] = useState(false)
  const [name, setName] = useState(deck.name)
  const [description, setDescription] = useState(deck.description ?? '')

  if (!editing) {
    return (
      <div className="flex items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-text-primary">{deck.name}</h1>
          {deck.description && <p className="text-sm text-text-faint">{deck.description}</p>}
        </div>
        <Button variant="secondary" onClick={() => setEditing(true)}>
          {t('common.action.edit')}
        </Button>
      </div>
    )
  }

  return (
    <form
      className="flex flex-col gap-3"
      onSubmit={(event) => {
        event.preventDefault()
        onSave(
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
        <Textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={2} />
      </label>
      <div className="flex justify-end gap-2">
        <Button type="button" variant="secondary" onClick={() => setEditing(false)}>
          {t('common.action.cancel')}
        </Button>
        <Button type="submit" disabled={isSaving}>
          {t('common.action.save')}
        </Button>
      </div>
    </form>
  )
}
