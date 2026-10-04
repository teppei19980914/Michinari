import { beforeEach, describe, expect, it, vi } from 'vitest'
import { screen } from '@testing-library/react'
import { t } from '../../locales/t'
import { apiErrorMessage } from '../../api/client'
import { renderWithProviders } from '../../test/renderWithProviders'
import { RecapThemeSection } from './RecapThemeSection'

const listRecapThemes = vi.hoisted(() => vi.fn())
vi.mock('../../api/recap', () => ({ listRecapThemes }))

describe('RecapThemeSection', () => {
  beforeEach(() => {
    listRecapThemes.mockReset()
  })

  it('shows the loading text while the themes are fetched', () => {
    listRecapThemes.mockReturnValue(new Promise(() => {}))
    renderWithProviders(<RecapThemeSection goalId={10} />)

    expect(screen.getByText(t('common.loading'))).toBeDefined()
  })

  it('shows the error message when the themes cannot be fetched', async () => {
    const error = new Error('取得に失敗')
    listRecapThemes.mockRejectedValue(error)
    renderWithProviders(<RecapThemeSection goalId={10} />)

    expect(await screen.findByText(apiErrorMessage(error))).toBeDefined()
  })

  it('shows the empty message when there are no themes yet', async () => {
    listRecapThemes.mockResolvedValue([])
    renderWithProviders(<RecapThemeSection goalId={10} />)

    expect(await screen.findByText(t('dashboard.recapThemes.empty'))).toBeDefined()
  })

  it('lists the themes as links to their detail pages with report counts', async () => {
    listRecapThemes.mockResolvedValue([
      { id: 7, name: 'メール関連', entry_count: 3, updated_at: '2026-03-10T00:00:00' },
    ])
    renderWithProviders(<RecapThemeSection goalId={10} />)

    const link = await screen.findByRole('link', { name: 'メール関連' })
    expect(link.getAttribute('href')).toBe('/recap-themes/7')
    expect(screen.getByText(t('dashboard.recapThemes.entryCount', { count: 3 }))).toBeDefined()
    expect(listRecapThemes).toHaveBeenCalledWith(10)
  })
})
