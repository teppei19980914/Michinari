import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, screen } from '@testing-library/react'
import { t } from '../locales/t'
import { apiErrorMessage } from '../api/client'
import { ROUTES } from '../constants/routes'
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

  it('links a goal directly to its quiz setup screen, not the goal detail page', async () => {
    /** 開発Todo_単語帳_出題導線改修_v1.0 U6：目標詳細を経由せず問題出題内容設定画面
     * （中継ページ経由）へ直接遷移すること。 */
    listGoals.mockResolvedValue([{ id: 1, name: '資格目標', category: 'EXAM' }])
    renderWithProviders(<VocabHomePage />)

    const link = (await screen.findByText('資格目標')).closest('a')

    expect(link?.getAttribute('href')).toBe(ROUTES.vocabGoalQuiz(1))
  })
})
