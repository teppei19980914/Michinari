import { beforeEach, describe, expect, it, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes } from 'react-router-dom'
import { t } from '../locales/t'
import { ROUTE_PATTERNS } from '../constants/routes'
import { renderWithProviders } from '../test/renderWithProviders'
import { RecapThemeDetailPage } from './RecapThemeDetailPage'

const getRecapTheme = vi.hoisted(() => vi.fn())
const listRecapThemes = vi.hoisted(() => vi.fn())
const renameRecapTheme = vi.hoisted(() => vi.fn())
const mergeRecapTheme = vi.hoisted(() => vi.fn())
const rebuildRecapTheme = vi.hoisted(() => vi.fn())
vi.mock('../api/recap', () => ({
  getRecapTheme,
  listRecapThemes,
  renameRecapTheme,
  mergeRecapTheme,
  rebuildRecapTheme,
}))

function makeDetail(overrides: Partial<Record<string, unknown>> = {}) {
  return {
    id: 1,
    goal_id: 10,
    name: 'メール関連',
    body: '・SMTP（2026-03-09）',
    updated_at: '2026-03-10T00:00:00',
    entries: [{ source_kind: 'DIARY', record_date: '2026-03-09', text: 'SMTPの役割' }],
    ...overrides,
  }
}

function renderPage(themeId = '1') {
  return renderWithProviders(
    <Routes>
      <Route path={ROUTE_PATTERNS.recapTheme} element={<RecapThemeDetailPage />} />
      <Route path={ROUTE_PATTERNS.dashboard} element={<p>dashboard-marker</p>} />
    </Routes>,
    { initialEntries: [`/recap-themes/${themeId}`] },
  )
}

describe('RecapThemeDetailPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    listRecapThemes.mockResolvedValue([
      { id: 1, name: 'メール関連', entry_count: 1, updated_at: '2026-03-10T00:00:00' },
      { id: 2, name: '認証', entry_count: 2, updated_at: '2026-03-09T00:00:00' },
    ])
  })

  it('shows loading and then the theme body and its source reports', async () => {
    getRecapTheme.mockResolvedValue(makeDetail())
    renderPage()

    expect(await screen.findByText('SMTPの役割')).toBeDefined()
    expect(screen.getByRole('heading', { name: 'メール関連' })).toBeDefined()
    expect(screen.getByText(t('recapTheme.sourceKind.DIARY'), { exact: false })).toBeDefined()
  })

  it('shows the error message when the theme cannot be loaded', async () => {
    getRecapTheme.mockRejectedValue(new Error('取得に失敗'))
    renderPage()

    expect(await screen.findByText(/取得に失敗|エラー|失敗/)).toBeDefined()
  })

  it('shows the empty body and empty entries messages', async () => {
    getRecapTheme.mockResolvedValue(makeDetail({ body: '  ', entries: [] }))
    renderPage()

    expect(await screen.findByText(t('recapTheme.bodyEmpty'))).toBeDefined()
    expect(screen.getByText(t('recapTheme.entriesEmpty'))).toBeDefined()
  })

  it('renames the theme', async () => {
    const user = userEvent.setup()
    getRecapTheme.mockResolvedValue(makeDetail())
    renameRecapTheme.mockResolvedValue(makeDetail({ name: 'メール' }))
    renderPage()

    const input = await screen.findByLabelText(t('recapTheme.renameLabel'))
    await user.clear(input)
    await user.type(input, 'メール')
    await user.click(screen.getByRole('button', { name: t('recapTheme.renameButton') }))

    await waitFor(() => expect(renameRecapTheme).toHaveBeenCalledWith(1, 'メール'))
  })

  it('merges into the chosen theme after confirmation', async () => {
    const user = userEvent.setup()
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    getRecapTheme.mockResolvedValue(makeDetail())
    mergeRecapTheme.mockResolvedValue(makeDetail({ id: 2, name: '認証' }))
    renderPage()

    await screen.findByText('SMTPの役割')
    await waitFor(() => expect(listRecapThemes).toHaveBeenCalledWith(10))
    const select = await screen.findByRole('combobox')
    await user.selectOptions(select, '2')
    await user.click(screen.getByRole('button', { name: t('recapTheme.mergeButton') }))

    await waitFor(() => expect(mergeRecapTheme).toHaveBeenCalledWith(1, 2))
  })

  it('does not merge when the confirmation is cancelled', async () => {
    const user = userEvent.setup()
    vi.spyOn(window, 'confirm').mockReturnValue(false)
    getRecapTheme.mockResolvedValue(makeDetail())
    renderPage()

    const select = await screen.findByRole('combobox')
    await waitFor(() => expect(screen.getByRole('option', { name: '認証' })).toBeDefined())
    await user.selectOptions(select, '2')
    await user.click(screen.getByRole('button', { name: t('recapTheme.mergeButton') }))

    expect(mergeRecapTheme).not.toHaveBeenCalled()
  })

  it('rebuilds the body after confirmation', async () => {
    const user = userEvent.setup()
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    getRecapTheme.mockResolvedValue(makeDetail())
    rebuildRecapTheme.mockResolvedValue(makeDetail({ body: '・再構築' }))
    renderPage()

    await user.click(await screen.findByRole('button', { name: t('recapTheme.rebuildButton') }))

    await waitFor(() => expect(rebuildRecapTheme).toHaveBeenCalledWith(1))
  })
})
