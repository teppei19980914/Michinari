import { afterEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { t } from '../../locales/t'
import { RecapThemeEditCard } from './RecapThemeEditCard'

const candidates = [{ id: 2, name: '認証', entry_count: 1, updated_at: '2026-03-10T00:00:00' }]

function renderCard(overrides: Partial<Parameters<typeof RecapThemeEditCard>[0]> = {}) {
  const handlers = { onRename: vi.fn(), onMerge: vi.fn(), onRebuild: vi.fn() }
  render(
    <RecapThemeEditCard
      themeName="メール関連"
      mergeCandidates={candidates}
      isSaving={false}
      {...handlers}
      {...overrides}
    />,
  )
  return handlers
}

describe('RecapThemeEditCard', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('keeps the rename button disabled until the name is changed', async () => {
    const user = userEvent.setup()
    const { onRename } = renderCard()
    const button = screen.getByRole('button', { name: t('recapTheme.renameButton') })
    expect((button as HTMLButtonElement).disabled).toBe(true)

    await user.type(screen.getByLabelText(t('recapTheme.renameLabel')), 'X')
    expect((button as HTMLButtonElement).disabled).toBe(false)
    await user.click(button)

    expect(onRename).toHaveBeenCalledWith('メール関連X')
  })

  it('disables the rename button for a blank name', async () => {
    const user = userEvent.setup()
    renderCard()
    const input = screen.getByLabelText(t('recapTheme.renameLabel'))
    await user.clear(input)

    expect(
      (screen.getByRole('button', { name: t('recapTheme.renameButton') }) as HTMLButtonElement)
        .disabled,
    ).toBe(true)
  })

  it('merges only after the user picks a target and confirms', async () => {
    const user = userEvent.setup()
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    const { onMerge } = renderCard()
    const mergeButton = screen.getByRole('button', { name: t('recapTheme.mergeButton') })
    expect((mergeButton as HTMLButtonElement).disabled).toBe(true)

    await user.selectOptions(screen.getByRole('combobox'), '2')
    await user.click(mergeButton)

    expect(onMerge).toHaveBeenCalledWith(2)
  })

  it('does not merge when the confirmation is declined', async () => {
    const user = userEvent.setup()
    vi.spyOn(window, 'confirm').mockReturnValue(false)
    const { onMerge } = renderCard()

    await user.selectOptions(screen.getByRole('combobox'), '2')
    await user.click(screen.getByRole('button', { name: t('recapTheme.mergeButton') }))

    expect(onMerge).not.toHaveBeenCalled()
  })

  it('clears the merge target when the placeholder is chosen again', async () => {
    const user = userEvent.setup()
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    const { onMerge } = renderCard()
    const select = screen.getByRole('combobox')

    await user.selectOptions(select, '2')
    await user.selectOptions(select, '')

    expect(
      (screen.getByRole('button', { name: t('recapTheme.mergeButton') }) as HTMLButtonElement)
        .disabled,
    ).toBe(true)
    expect(onMerge).not.toHaveBeenCalled()
  })

  it('rebuilds only after confirmation and disables actions while saving', async () => {
    const user = userEvent.setup()
    vi.spyOn(window, 'confirm').mockReturnValueOnce(false).mockReturnValueOnce(true)
    const { onRebuild } = renderCard()
    const button = screen.getByRole('button', { name: t('recapTheme.rebuildButton') })

    await user.click(button)
    expect(onRebuild).not.toHaveBeenCalled()
    await user.click(button)
    expect(onRebuild).toHaveBeenCalledTimes(1)
  })

  it('disables every action while a save is in progress', () => {
    renderCard({ isSaving: true })

    expect(
      (screen.getByRole('button', { name: t('recapTheme.rebuildButton') }) as HTMLButtonElement)
        .disabled,
    ).toBe(true)
  })
})
