import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { t } from '../../locales/t'
import { VocabTermFields, type VocabTermFieldsValue } from './VocabTermFields'
import type { VocabDeck } from '../../api/vocab'

function makeDeck(id: number, name: string): VocabDeck {
  return {
    id,
    goal_id: 1,
    name,
    description: null,
    use_in_ai: true,
    display_order: 0,
    card_count: 0,
    mastered_card_count: 0,
    session_default_questions: 10,
    session_max_questions: 100,
  }
}

const DECKS = [makeDeck(1, 'デッキA'), makeDeck(2, 'デッキB')]

afterEach(() => {
  cleanup()
})

function renderFields(value: VocabTermFieldsValue, onChange: (value: VocabTermFieldsValue) => void) {
  render(<VocabTermFields decks={DECKS} value={value} onChange={onChange} />)
}

describe('VocabTermFields', () => {
  it('lists every deck as an option', () => {
    renderFields({ deckId: 1, term: '', meaning: '', aliases: '' }, vi.fn())

    expect(screen.getByRole('option', { name: 'デッキA' })).toBeTruthy()
    expect(screen.getByRole('option', { name: 'デッキB' })).toBeTruthy()
  })

  it('reports the chosen deck id', async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()
    renderFields({ deckId: 1, term: '', meaning: '', aliases: '' }, onChange)

    await user.selectOptions(screen.getByLabelText(t('vocab.suggestions.deckLabel')), 'デッキB')

    expect(onChange).toHaveBeenCalledWith({ deckId: 2, term: '', meaning: '', aliases: '' })
  })

  it('reports term/meaning/aliases edits', async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()
    renderFields({ deckId: 1, term: '', meaning: '', aliases: '' }, onChange)

    await user.type(screen.getByLabelText(t('vocab.suggestions.termLabel')), 'T')
    expect(onChange).toHaveBeenLastCalledWith({ deckId: 1, term: 'T', meaning: '', aliases: '' })

    await user.type(screen.getByLabelText(t('vocab.suggestions.meaningLabel')), 'M')
    expect(onChange).toHaveBeenLastCalledWith({ deckId: 1, term: '', meaning: 'M', aliases: '' })

    await user.type(screen.getByLabelText(t('vocab.suggestions.aliasesLabel')), 'A')
    expect(onChange).toHaveBeenLastCalledWith({ deckId: 1, term: '', meaning: '', aliases: 'A' })
  })
})
