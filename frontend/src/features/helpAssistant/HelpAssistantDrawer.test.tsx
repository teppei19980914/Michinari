/** ヘルプAIアシスタントのドロワーの描画テスト（Phase43、開発Todo F-03）。
 *
 * 通信は `api/helpAssistant` を差し替えて検証する。回答が「文字として」描画されること、
 * 生HTMLが実行・描画されないこと（XSS回帰）、固定文言が出ることを固定する。 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ApiError } from '../../api/client'
import { t } from '../../locales/t'
import { renderWithProviders } from '../../test/renderWithProviders'
import { HelpAssistantDrawer } from './HelpAssistantDrawer'

const askHelpQuestion = vi.hoisted(() => vi.fn())
const getHelpAssistantLimits = vi.hoisted(() => vi.fn())
vi.mock('../../api/helpAssistant', () => ({ askHelpQuestion, getHelpAssistantLimits }))

beforeEach(() => {
  getHelpAssistantLimits.mockResolvedValue({ max_question_chars: 300 })
})

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

/** 要素が無効化されているか（テストライブラリの拡張検証を使わず、属性で判定する）。 */
function isDisabled(element: HTMLElement): boolean {
  return (element as HTMLButtonElement | HTMLTextAreaElement).disabled
}

/** 上限が読めるまで待ってから、入力と送信を行う。 */
async function ask(text: string) {
  const user = userEvent.setup()
  await waitFor(() => expect(getHelpAssistantLimits).toHaveBeenCalled())
  await user.type(screen.getByRole('textbox', { name: t('helpAssistant.placeholder') }), text)
  await user.click(screen.getByRole('button', { name: t('helpAssistant.send') }))
}

describe('HelpAssistantDrawer', () => {
  it('ドロワーと免責文を表示し、入力が空のあいだは送信できない', async () => {
    renderWithProviders(<HelpAssistantDrawer onClose={() => {}} />)

    expect(screen.getByRole('dialog', { name: t('helpAssistant.title') })).toBeTruthy()
    expect(screen.getByText(t('helpAssistant.disclaimer'))).toBeTruthy()
    await waitFor(() => expect(getHelpAssistantLimits).toHaveBeenCalled())
    expect(isDisabled(screen.getByRole('button', { name: t('helpAssistant.send') }))).toBe(true)
  })

  it('回答本文と出典の見出しを表示する', async () => {
    askHelpQuestion.mockResolvedValue({
      status: 'ANSWERED',
      answer: '資格試験・読書・仕事の3種類です。',
      sections: [{ id: 'goals', title: '目標' }],
    })
    renderWithProviders(<HelpAssistantDrawer onClose={() => {}} />)

    await ask('目標は何種類ありますか')

    expect(await screen.findByText('資格試験・読書・仕事の3種類です。')).toBeTruthy()
    expect(screen.getByText(`${t('helpAssistant.sectionsLabel')}：目標`)).toBeTruthy()
    expect(askHelpQuestion).toHaveBeenCalledWith('目標は何種類ありますか')
  })

  it('記載なしの回答は固定文言とヘルプ画面への導線を出す', async () => {
    askHelpQuestion.mockResolvedValue({ status: 'NOT_FOUND', answer: null, sections: [] })
    renderWithProviders(<HelpAssistantDrawer onClose={() => {}} />)

    await ask('今日の天気は？')

    expect(await screen.findByText(t('helpAssistant.notFound'))).toBeTruthy()
    expect(screen.getByRole('link', { name: t('helpAssistant.helpLink') })).toBeTruthy()
  })

  it('表示できない回答は固定文言だけを出し、導線は出さない', async () => {
    askHelpQuestion.mockResolvedValue({ status: 'UNAVAILABLE', answer: null, sections: [] })
    renderWithProviders(<HelpAssistantDrawer onClose={() => {}} />)

    await ask('何か')

    expect(await screen.findByText(t('helpAssistant.unavailable'))).toBeTruthy()
    expect(screen.queryByRole('link', { name: t('helpAssistant.helpLink') })).toBeNull()
  })

  it('AI未接続のエラーは接続案内を出す', async () => {
    askHelpQuestion.mockRejectedValue(new ApiError('AI_AUTH_REQUIRED', 'x'))
    renderWithProviders(<HelpAssistantDrawer onClose={() => {}} />)

    await ask('目標は？')

    expect(await screen.findByText(t('helpAssistant.authRequired'))).toBeTruthy()
  })

  it('それ以外の通信エラーは汎用の失敗文言を出す', async () => {
    askHelpQuestion.mockRejectedValue(new Error('network'))
    renderWithProviders(<HelpAssistantDrawer onClose={() => {}} />)

    await ask('目標は？')

    expect(await screen.findByText(t('helpAssistant.error'))).toBeTruthy()
  })

  it('回答に含まれるHTMLは描画されない（XSSの回帰）', async () => {
    askHelpQuestion.mockResolvedValue({
      status: 'ANSWERED',
      answer: '<img src="x" onerror="alert(1)"> 本文 [危険](javascript:alert(1))',
      sections: [{ id: 'goals', title: '目標' }],
    })
    renderWithProviders(<HelpAssistantDrawer onClose={() => {}} />)

    await ask('危険な回答')

    await screen.findByText(/本文/)
    expect(document.querySelector('img[onerror]')).toBeNull()
    expect(document.querySelector('a[href^="javascript:"]')).toBeNull()
  })

  it('質問の上限を超える入力は警告を出し、送信できない', async () => {
    renderWithProviders(<HelpAssistantDrawer onClose={() => {}} />)
    await waitFor(() => expect(getHelpAssistantLimits).toHaveBeenCalled())

    // 301字を1字ずつ打つと時間がかかるため、値を一度に入れる（検証したいのは最終的な状態）
    fireEvent.change(screen.getByRole('textbox', { name: t('helpAssistant.placeholder') }), {
      target: { value: 'あ'.repeat(301) },
    })

    expect(screen.getByText(t('helpAssistant.tooLong', { max: 300 }))).toBeTruthy()
    expect(isDisabled(screen.getByRole('button', { name: t('helpAssistant.send') }))).toBe(true)
    expect(askHelpQuestion).not.toHaveBeenCalled()
  })

  it('送信中は入力を無効化し、送信中の表示を出す', async () => {
    askHelpQuestion.mockReturnValue(new Promise(() => {}))
    renderWithProviders(<HelpAssistantDrawer onClose={() => {}} />)

    await ask('目標は？')

    expect(await screen.findByText(t('helpAssistant.sending'))).toBeTruthy()
    expect(isDisabled(screen.getByRole('textbox', { name: t('helpAssistant.placeholder') }))).toBe(true)
  })

  it('閉じるボタンで onClose を呼ぶ', async () => {
    const onClose = vi.fn()
    renderWithProviders(<HelpAssistantDrawer onClose={onClose} />)

    await userEvent.setup().click(screen.getByRole('button', { name: t('helpAssistant.close') }))

    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('出典が無い回答は本文だけを出し、出典の見出しは出さない', async () => {
    askHelpQuestion.mockResolvedValue({ status: 'ANSWERED', answer: '本文だけです。', sections: [] })
    renderWithProviders(<HelpAssistantDrawer onClose={() => {}} />)

    await ask('根拠のない質問')

    expect(await screen.findByText('本文だけです。')).toBeTruthy()
    expect(screen.queryByText(new RegExp(t('helpAssistant.sectionsLabel')))).toBeNull()
  })

  it('本文が無いのに ANSWERED と返された回答は、表示できない回答として扱う', async () => {
    askHelpQuestion.mockResolvedValue({ status: 'ANSWERED', answer: null, sections: [] })
    renderWithProviders(<HelpAssistantDrawer onClose={() => {}} />)

    await ask('本文のない回答')

    expect(await screen.findByText(t('helpAssistant.unavailable'))).toBeTruthy()
  })

  it('新しい回答が積まれたら最新が見えるようスクロールする', async () => {
    askHelpQuestion.mockResolvedValue({
      status: 'ANSWERED',
      answer: '資格試験・読書・仕事の3種類です。',
      sections: [{ id: 'goals', title: '目標' }],
    })
    renderWithProviders(<HelpAssistantDrawer onClose={() => {}} />)

    await ask('目標は何種類ありますか')
    const container = (await screen.findByText('資格試験・読書・仕事の3種類です。')).closest(
      '.overflow-y-auto',
    ) as HTMLDivElement
    Object.defineProperty(container, 'scrollHeight', { value: 999, configurable: true })
    container.scrollTop = 0

    await ask('もう一つ質問')

    await waitFor(() => expect(container.scrollTop).toBe(999))
  })

  it('送信できない状態でフォームを送信しても、質問は送られない', async () => {
    renderWithProviders(<HelpAssistantDrawer onClose={() => {}} />)
    await waitFor(() => expect(getHelpAssistantLimits).toHaveBeenCalled())

    fireEvent.submit(screen.getByRole('button', { name: t('helpAssistant.send') }).closest('form')!)

    expect(askHelpQuestion).not.toHaveBeenCalled()
  })
})
