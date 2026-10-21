/** 目標相談チャットのタブの描画テスト（S09、開発Todo F-03）。
 *
 * 通信は`api/goalConsultation`を差し替えて検証する。回答が「文字として」描画されること、
 * 生HTMLが実行・描画されないこと（XSS回帰）、根拠の日付が日次報告の閲覧画面へのリンクに
 * なること、AI未接続時に案内が出ることを固定する（`HelpAssistantDrawer.test.tsx`と同じ方針）。 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ApiError } from '../../api/client'
import { t } from '../../locales/t'
import { ROUTES } from '../../constants/routes'
import { renderWithProviders } from '../../test/renderWithProviders'
import { GoalConsultationTab } from './GoalConsultationTab'

const askGoalConsultationQuestion = vi.hoisted(() => vi.fn())
const getGoalConsultationLimits = vi.hoisted(() => vi.fn())
vi.mock('../../api/goalConsultation', () => ({
  askGoalConsultationQuestion,
  getGoalConsultationLimits,
}))

const getAiStatus = vi.hoisted(() => vi.fn())
vi.mock('../../api/ai', () => ({ getAiStatus }))

const GOAL_ID = 42

beforeEach(() => {
  getGoalConsultationLimits.mockResolvedValue({ max_question_chars: 300 })
  getAiStatus.mockResolvedValue({ authenticated: true, model_status: {}, login_in_progress: false })
})

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

function isDisabled(element: HTMLElement): boolean {
  return (element as HTMLButtonElement | HTMLTextAreaElement).disabled
}

async function ask(text: string) {
  const user = userEvent.setup()
  await waitFor(() => expect(getGoalConsultationLimits).toHaveBeenCalled())
  await user.type(screen.getByRole('textbox', { name: t('goalConsultation.placeholder') }), text)
  await user.click(screen.getByRole('button', { name: t('goalConsultation.send') }))
}

describe('GoalConsultationTab', () => {
  it('タイトルと免責文を表示し、入力が空のあいだは送信できない', async () => {
    renderWithProviders(<GoalConsultationTab goalId={GOAL_ID} />)

    expect(await screen.findByText(t('goalConsultation.disclaimer'))).toBeTruthy()
    expect(screen.getByText(t('goalConsultation.noHistoryYet'))).toBeTruthy()
    await waitFor(() => expect(getGoalConsultationLimits).toHaveBeenCalled())
    expect(isDisabled(screen.getByRole('button', { name: t('goalConsultation.send') }))).toBe(
      true,
    )
  })

  it('回答本文と根拠の日付（リンク）・週を表示する', async () => {
    askGoalConsultationQuestion.mockResolvedValue({
      status: 'ANSWERED',
      answer: '## 記録から言えること\n順調です。',
      cited_dates: ['2026-01-15'],
      cited_weeks: [{ start: '2026-01-05', end: '2026-01-11' }],
    })
    renderWithProviders(<GoalConsultationTab goalId={GOAL_ID} />)

    await ask('この後何を勉強すべき？')

    expect(await screen.findByText(/順調です/)).toBeTruthy()
    const link = screen.getByRole('link', { name: '2026-01-15' })
    expect(link.getAttribute('href')).toBe(ROUTES.dailyReportView('2026-01-15'))
    expect(screen.getByText('2026-01-05〜2026-01-11')).toBeTruthy()
    expect(askGoalConsultationQuestion).toHaveBeenCalledWith(GOAL_ID, 'この後何を勉強すべき？')
  })

  it('表示できない回答は固定文言だけを出す', async () => {
    askGoalConsultationQuestion.mockResolvedValue({
      status: 'UNAVAILABLE',
      answer: null,
      cited_dates: [],
      cited_weeks: [],
    })
    renderWithProviders(<GoalConsultationTab goalId={GOAL_ID} />)

    await ask('何か')

    expect(await screen.findByText(t('goalConsultation.unavailable'))).toBeTruthy()
  })

  it('根拠が無い回答は根拠欄を出さない', async () => {
    askGoalConsultationQuestion.mockResolvedValue({
      status: 'ANSWERED',
      answer: '一般的な助言のみです。',
      cited_dates: [],
      cited_weeks: [],
    })
    renderWithProviders(<GoalConsultationTab goalId={GOAL_ID} />)

    await ask('根拠のない質問')

    expect(await screen.findByText('一般的な助言のみです。')).toBeTruthy()
    expect(screen.queryByText(`${t('goalConsultation.citationsLabel')}：`)).toBeNull()
  })

  it('本文が無いのにANSWEREDと返された回答は、表示できない回答として扱う', async () => {
    askGoalConsultationQuestion.mockResolvedValue({
      status: 'ANSWERED',
      answer: null,
      cited_dates: [],
      cited_weeks: [],
    })
    renderWithProviders(<GoalConsultationTab goalId={GOAL_ID} />)

    await ask('本文のない回答')

    expect(await screen.findByText(t('goalConsultation.unavailable'))).toBeTruthy()
  })

  it('AI未接続のエラーは接続案内を出す', async () => {
    askGoalConsultationQuestion.mockRejectedValue(new ApiError('AI_AUTH_REQUIRED', 'x'))
    renderWithProviders(<GoalConsultationTab goalId={GOAL_ID} />)

    await ask('質問')

    expect(await screen.findByText(t('goalConsultation.authRequired'))).toBeTruthy()
  })

  it('それ以外の通信エラーは汎用の失敗文言を出す', async () => {
    askGoalConsultationQuestion.mockRejectedValue(new Error('network'))
    renderWithProviders(<GoalConsultationTab goalId={GOAL_ID} />)

    await ask('質問')

    expect(await screen.findByText(t('goalConsultation.error'))).toBeTruthy()
  })

  it('回答に含まれるHTMLは描画されない（XSSの回帰）', async () => {
    askGoalConsultationQuestion.mockResolvedValue({
      status: 'ANSWERED',
      answer: '<img src="x" onerror="alert(1)"> 本文 [危険](javascript:alert(1))',
      cited_dates: [],
      cited_weeks: [],
    })
    renderWithProviders(<GoalConsultationTab goalId={GOAL_ID} />)

    await ask('危険な回答')

    await screen.findByText(/本文/)
    expect(document.querySelector('img[onerror]')).toBeNull()
    expect(document.querySelector('a[href^="javascript:"]')).toBeNull()
  })

  it('質問の上限を超える入力は警告を出し、送信できない', async () => {
    renderWithProviders(<GoalConsultationTab goalId={GOAL_ID} />)
    await waitFor(() => expect(getGoalConsultationLimits).toHaveBeenCalled())

    fireEvent.change(screen.getByRole('textbox', { name: t('goalConsultation.placeholder') }), {
      target: { value: 'あ'.repeat(301) },
    })

    expect(screen.getByText(t('goalConsultation.tooLong', { max: 300 }))).toBeTruthy()
    expect(isDisabled(screen.getByRole('button', { name: t('goalConsultation.send') }))).toBe(
      true,
    )
    expect(askGoalConsultationQuestion).not.toHaveBeenCalled()
  })

  it('送信中は入力を無効化し、送信中の表示を出す', async () => {
    askGoalConsultationQuestion.mockReturnValue(new Promise(() => {}))
    renderWithProviders(<GoalConsultationTab goalId={GOAL_ID} />)

    await ask('質問')

    expect(await screen.findByText(t('goalConsultation.sending'))).toBeTruthy()
    expect(
      isDisabled(screen.getByRole('textbox', { name: t('goalConsultation.placeholder') })),
    ).toBe(true)
  })

  it('AI未接続時は入力欄の代わりに案内を出す', async () => {
    getAiStatus.mockResolvedValue({
      authenticated: false,
      model_status: {},
      login_in_progress: false,
    })
    renderWithProviders(<GoalConsultationTab goalId={GOAL_ID} />)

    expect(await screen.findByText(t('aiUnconfigured.message'))).toBeTruthy()
    expect(screen.queryByRole('textbox', { name: t('goalConsultation.placeholder') })).toBeNull()
  })

  it('送信できない状態でフォームを送信しても、質問は送られない', async () => {
    renderWithProviders(<GoalConsultationTab goalId={GOAL_ID} />)
    await waitFor(() => expect(getGoalConsultationLimits).toHaveBeenCalled())

    fireEvent.submit(
      screen.getByRole('button', { name: t('goalConsultation.send') }).closest('form')!,
    )

    expect(askGoalConsultationQuestion).not.toHaveBeenCalled()
  })
})
