/** ヘルプ画面からウェルカム画面へ再アクセスできることを固定する（既存ユーザ・開発者が
 * 使い方を再確認できるようにする導線。仕様書「初回起動時のウェルカム画面」）。 */
import { describe, expect, it } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes } from 'react-router-dom'
import { t } from '../locales/t'
import { ROUTE_PATTERNS } from '../constants/routes'
import { renderWithProviders } from '../test/renderWithProviders'
import { HelpPage } from './HelpPage'

const WELCOME_MARKER = 'welcome-marker'

function renderPage() {
  return renderWithProviders(
    <Routes>
      <Route path={ROUTE_PATTERNS.help} element={<HelpPage />} />
      <Route path={ROUTE_PATTERNS.welcome} element={<p>{WELCOME_MARKER}</p>} />
    </Routes>,
    { initialEntries: [ROUTE_PATTERNS.help] },
  )
}

describe('HelpPage のウェルカム画面への再アクセス', () => {
  it('navigates to /welcome when the reopen link is clicked', async () => {
    const user = userEvent.setup()
    renderPage()

    await user.click(screen.getByText(t('welcome.reopenLink')))

    expect(await screen.findByText(WELCOME_MARKER)).toBeDefined()
  })
})
