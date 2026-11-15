import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, screen } from '@testing-library/react'
import { t } from '../locales/t'
import { apiErrorMessage } from '../api/client'
import { renderWithProviders } from '../test/renderWithProviders'
import { VocabHomePage } from './VocabHomePage'

const listGoals = vi.hoisted(() => vi.fn())
vi.mock('../api/goals', () => ({ listGoals }))

beforeEach(() => {
  vi.clearAllMocks()
})

afterEach(() => {
  cleanup()
})

describe('VocabHomePage', () => {
  it('shows the loading text while fetching', () => {
    listGoals.mockReturnValue(new Promise(() => {}))
    renderWithProviders(<VocabHomePage />)

    expect(screen.getByText(t('common.loading'))).toBeDefined()
  })

  it('shows an error message when fetching fails', async () => {
    const error = new Error('取得失敗')
    listGoals.mockRejectedValue(error)
    renderWithProviders(<VocabHomePage />)

    expect(await screen.findByText(apiErrorMessage(error))).toBeDefined()
  })

  it('shows the empty message when there is no exam goal', async () => {
    listGoals.mockResolvedValue([{ id: 1, name: '読書目標', category: 'READING' }])
    renderWithProviders(<VocabHomePage />)

    expect(await screen.findByText(t('vocab.home.empty'))).toBeDefined()
  })

  it('lists only exam goals', async () => {
    listGoals.mockResolvedValue([
      { id: 1, name: '資格目標', category: 'EXAM' },
      { id: 2, name: '読書目標', category: 'READING' },
    ])
    renderWithProviders(<VocabHomePage />)

    expect(await screen.findByText('資格目標')).toBeDefined()
    expect(screen.queryByText('読書目標')).toBeNull()
  })
})
