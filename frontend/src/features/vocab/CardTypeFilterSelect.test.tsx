import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { t } from '../../locales/t'
import { CardTypeFilterSelect } from './CardTypeFilterSelect'

afterEach(() => {
  cleanup()
})

describe('CardTypeFilterSelect', () => {
  it('lists ALL/TERM/SITUATION and calls onChange with the selected key', async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()
    render(<CardTypeFilterSelect label="種類" value="ALL" onChange={onChange} />)

    expect(screen.getByRole('option', { name: t('vocab.deckDetail.cardTypeOptions.SITUATION') })).toBeTruthy()

    await user.selectOptions(
      screen.getByLabelText('種類'),
      t('vocab.deckDetail.cardTypeOptions.TERM'),
    )

    expect(onChange).toHaveBeenCalledWith('TERM')
  })
})
