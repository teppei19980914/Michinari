/** 「ヘルプに質問する」ボタンの開閉の描画テスト（Phase43、開発Todo F-04）。 */
import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { t } from '../../locales/t'
import { renderWithProviders } from '../../test/renderWithProviders'
import { HelpAssistantLauncher } from './HelpAssistantLauncher'

vi.mock('../../api/helpAssistant', () => ({
  askHelpQuestion: vi.fn(),
  getHelpAssistantLimits: vi.fn().mockResolvedValue({ max_question_chars: 300 }),
}))

afterEach(() => {
  cleanup()
})

describe('HelpAssistantLauncher', () => {
  it('ボタンを押すとドロワーが開き、閉じるとボタンに戻る', async () => {
    const user = userEvent.setup()
    renderWithProviders(<HelpAssistantLauncher />)

    await user.click(screen.getByRole('button', { name: t('helpAssistant.launcherLabel') }))
    expect(screen.getByRole('dialog', { name: t('helpAssistant.title') })).toBeTruthy()
    expect(screen.queryByRole('button', { name: t('helpAssistant.launcherLabel') })).toBeNull()

    await user.click(screen.getByRole('button', { name: t('helpAssistant.close') }))
    expect(screen.queryByRole('dialog')).toBeNull()
    expect(screen.getByRole('button', { name: t('helpAssistant.launcherLabel') })).toBeTruthy()
  })
})
