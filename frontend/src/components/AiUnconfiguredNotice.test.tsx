/** AI未設定時の案内（完了条件D）。全画面で使い回すため、ここで一度だけ振る舞いを固定する。 */
import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { t } from '../locales/t'
import { ROUTE_PATTERNS } from '../constants/routes'
import { AiUnconfiguredNotice } from './AiUnconfiguredNotice'

const navigate = vi.hoisted(() => vi.fn())
vi.mock('react-router-dom', async (importOriginal) => ({
  ...(await importOriginal<typeof import('react-router-dom')>()),
  useNavigate: () => navigate,
}))

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('AiUnconfiguredNotice', () => {
  it('explains that AI setup is needed but recording still works', () => {
    render(<AiUnconfiguredNotice />)

    expect(screen.getByText(t('aiUnconfigured.message'))).toBeTruthy()
    expect(screen.getByText(t('aiUnconfigured.recordingStillWorks'))).toBeTruthy()
  })

  it('navigates to the settings screen when the button is clicked', async () => {
    const user = userEvent.setup()
    render(<AiUnconfiguredNotice />)

    await user.click(screen.getByRole('button', { name: t('aiUnconfigured.settingsButton') }))

    expect(navigate).toHaveBeenCalledWith(ROUTE_PATTERNS.settings)
  })
})
