/** デスクトップ・通知設定（SC-11、実装スコープA〜C）の表示と送信内容を固定する（Phase37）。
 *
 * この画面は4つの設定を1つの保存操作でまとめて送る。どれか1つでも送信先のキーを取り違えると、
 * 画面上は同じ形のチェックボックスが並ぶだけで気づけないまま、「自動起動をオンにしたのに
 * 起動しない」「通知を切ったのに来る」という形で利用者に現れる。送信内容まで含めて固定する。 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { act, cleanup, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { t } from '../../locales/t'
import { renderWithProviders } from '../../test/renderWithProviders'
import type { AppSettingsRead } from '../../api/settings'
import { DesktopSection } from './DesktopSection'

const updateSettings = vi.hoisted(() => vi.fn())
vi.mock('../../api/settings', () => ({ updateSettings }))

function makeDesktop(
  overrides: Partial<AppSettingsRead['desktop']> = {},
): AppSettingsRead['desktop'] {
  return {
    open_browser_on_startup: true,
    launch_at_login: false,
    notification_enabled: true,
    notification_time: '21:00',
    ...overrides,
  }
}

function renderSection(overrides: Partial<AppSettingsRead['desktop']> = {}) {
  return renderWithProviders(
    <DesktopSection settings={{ desktop: makeDesktop(overrides) } as AppSettingsRead} />,
  )
}

// --- 要素アクセサ ---
const openBrowserCheckbox = () =>
  screen.getByLabelText(t('settings.desktop.openBrowserLabel')) as HTMLInputElement
const launchAtLoginCheckbox = () =>
  screen.getByLabelText(t('settings.desktop.launchAtLoginLabel')) as HTMLInputElement
const notificationCheckbox = () =>
  screen.getByLabelText(t('settings.desktop.notificationEnabledLabel')) as HTMLInputElement
const notificationTimeInput = () =>
  screen.getByLabelText(t('settings.desktop.notificationTimeLabel')) as HTMLInputElement
const saveButton = () => screen.getByRole('button', { name: t('common.action.save') })

beforeEach(() => {
  vi.clearAllMocks()
  updateSettings.mockResolvedValue(undefined)
})

afterEach(() => {
  cleanup()
})

describe('DesktopSection の初期表示', () => {
  it('shows the section heading', () => {
    renderSection()
    expect(screen.getByText(t('settings.desktop.title'))).toBeTruthy()
  })

  it('reflects the stored values', () => {
    renderSection({
      open_browser_on_startup: false,
      launch_at_login: true,
      notification_enabled: false,
      notification_time: '07:30',
    })

    expect(openBrowserCheckbox().checked).toBe(false)
    expect(launchAtLoginCheckbox().checked).toBe(true)
    expect(notificationCheckbox().checked).toBe(false)
    expect(notificationTimeInput().value).toBe('07:30')
  })

  it('defaults automatic startup to off', () => {
    // 利用者の端末へ手を入れる設定のため、既定は無効（明示的に有効化されるまで登録しない）。
    renderSection()
    expect(launchAtLoginCheckbox().checked).toBe(false)
  })

  it('disables the time input while notifications are off', () => {
    renderSection({ notification_enabled: false })
    expect(notificationTimeInput().disabled).toBe(true)
  })

  it('enables the time input while notifications are on', () => {
    renderSection({ notification_enabled: true })
    expect(notificationTimeInput().disabled).toBe(false)
  })
})

describe('DesktopSection の保存', () => {
  it('sends every setting under the desktop group', async () => {
    const user = userEvent.setup()
    renderSection()

    await user.click(saveButton())

    await waitFor(() =>
      expect(updateSettings).toHaveBeenCalledWith({
        desktop: {
          open_browser_on_startup: true,
          launch_at_login: false,
          notification_enabled: true,
          notification_time: '21:00',
        },
      }),
    )
  })

  it('sends the toggled values rather than the initial ones', async () => {
    const user = userEvent.setup()
    renderSection()

    await user.click(openBrowserCheckbox())
    await user.click(launchAtLoginCheckbox())
    await user.click(saveButton())

    await waitFor(() =>
      expect(updateSettings).toHaveBeenCalledWith({
        desktop: {
          open_browser_on_startup: false,
          launch_at_login: true,
          notification_enabled: true,
          notification_time: '21:00',
        },
      }),
    )
  })

  it('sends an edited notification time', async () => {
    const user = userEvent.setup()
    renderSection()

    await user.clear(notificationTimeInput())
    await user.type(notificationTimeInput(), '07:30')
    await user.click(saveButton())

    await waitFor(() =>
      expect(updateSettings).toHaveBeenCalledWith(
        expect.objectContaining({
          desktop: expect.objectContaining({ notification_time: '07:30' }),
        }),
      ),
    )
  })

  it('reports success after saving', async () => {
    const user = userEvent.setup()
    renderSection()

    await user.click(saveButton())

    expect(await screen.findByText(t('common.saveSucceeded'))).toBeTruthy()
  })

  it('blocks saving while the notification time is incomplete', async () => {
    const user = userEvent.setup()
    renderSection()

    await user.clear(notificationTimeInput())

    expect(screen.getByText(t('settings.desktop.notificationTimeInvalid'))).toBeTruthy()
    expect((saveButton() as HTMLButtonElement).disabled).toBe(true)
    // 無効なボタンを実際に押しても送信されないことまで確かめる。押さずに
    // not.toHaveBeenCalled を書くと、ガードが外れていても自明に通ってしまう
    // （CODING_RULES.md「落ちないテストに注意する」）。
    await user.click(saveButton())
    await act(async () => {
      await Promise.resolve()
    })
    expect(updateSettings).not.toHaveBeenCalled()
  })

  it('saves with an empty time once notifications are turned off', async () => {
    // 通知を切った利用者が時刻欄を空にしても保存できること。空文字を送るとサーバの
    // スキーマ（min_length=1）が拒否するため、時刻は送らずに保存する。
    const user = userEvent.setup()
    renderSection()

    await user.clear(notificationTimeInput())
    await user.click(notificationCheckbox())

    expect(screen.queryByText(t('settings.desktop.notificationTimeInvalid'))).toBe(null)
    expect((saveButton() as HTMLButtonElement).disabled).toBe(false)

    await user.click(saveButton())

    await waitFor(() =>
      expect(updateSettings).toHaveBeenCalledWith({
        desktop: {
          open_browser_on_startup: true,
          launch_at_login: false,
          notification_enabled: false,
        },
      }),
    )
    expect(await screen.findByText(t('common.saveSucceeded'))).toBeTruthy()
  })

  it('surfaces a failure instead of reporting success', async () => {
    const user = userEvent.setup()
    updateSettings.mockRejectedValue(new Error('失敗'))
    renderSection()

    await user.click(saveButton())

    await waitFor(() => expect(updateSettings).toHaveBeenCalled())
    expect(screen.queryByText(t('common.saveSucceeded'))).toBe(null)
  })
})
