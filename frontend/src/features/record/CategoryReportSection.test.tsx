/** 3カテゴリ（資格試験・読書・仕事）で共有するセクション構成の振る舞いを固定する。
 *
 * 従来この出し分けは DailyReportPage 内に3回書かれていた。1箇所へ集約したことで、ここが
 * 壊れると3カテゴリすべてが同時に壊れるため、確定済み/未確定の切り替えと対話の開始→送信の
 * 遷移を直接検証する（vite.config.ts の「押した結果まで含めて守りたいもの」に該当）。 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { t } from '../../locales/t'
import type { ChatMessageRead } from '../../api/records'
import { CategoryReportSection, type CategoryReportSectionProps } from './CategoryReportSection'

const getAiStatus = vi.hoisted(() => vi.fn())
vi.mock('../../api/ai', () => ({ getAiStatus }))

const navigate = vi.hoisted(() => vi.fn())
vi.mock('react-router-dom', async (importOriginal) => ({
  ...(await importOriginal<typeof import('react-router-dom')>()),
  useNavigate: () => navigate,
}))

const LABELS = {
  title: t('dailyReport.readingLog.title'),
  chatTitle: t('dailyReport.readingChat.title'),
  chatStartLabel: t('dailyReport.readingChat.startButton'),
  finalizeLabel: t('dailyReport.readingLog.finalizeButton'),
}

const SUMMARY_MARKER = 'summary-content'
const EDITOR_MARKER = 'editor-content'

const MESSAGE: ChatMessageRead = {
  id: 1,
  goal_id: 1,
  purpose: 'DAILY_FEEDBACK_READING',
  role: 'ASSISTANT',
  content: 'assistant-content',
  sequence: 0,
  created_at: '2026-09-13T00:00:00Z',
}

/** 既定はAI接続済み（現行の大半のテストは既存の対話UIの振る舞いを検証するため）。
 * 未設定時の案内表示だけを検証するテストは、renderSection呼び出し前に上書きする。 */
function mockAiConfigured(authenticated = true) {
  getAiStatus.mockResolvedValue({ authenticated, model_status: {}, login_in_progress: false })
}

function renderSection(overrides: Partial<CategoryReportSectionProps> = {}) {
  const chat = { isPending: false, wasTruncated: false, contextCategories: [], send: vi.fn() }
  const finalize = { isPending: false, submit: vi.fn() }
  const queryClient = new QueryClient()
  render(
    <QueryClientProvider client={queryClient}>
      <CategoryReportSection
        labels={LABELS}
        isReported={false}
        summary={<p>{SUMMARY_MARKER}</p>}
        editor={<p>{EDITOR_MARKER}</p>}
        messages={[]}
        chat={chat}
        finalize={finalize}
        {...overrides}
      />
    </QueryClientProvider>,
  )
  return { chat, finalize }
}

beforeEach(() => {
  mockAiConfigured()
})

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('CategoryReportSection', () => {
  describe('while the category is not finalized', () => {
    it('shows the editor and the finalize button', () => {
      renderSection()

      expect(screen.getByText(EDITOR_MARKER)).toBeTruthy()
      expect(screen.queryByText(SUMMARY_MARKER)).toBe(null)
      expect(screen.queryByText(t('dailyReport.confirmedBadge'))).toBe(null)
      expect(screen.getByRole('button', { name: LABELS.finalizeLabel })).toBeTruthy()
    })

    it('finalizes the category when the button is pressed', async () => {
      const user = userEvent.setup()
      const { finalize } = renderSection()

      await user.click(screen.getByRole('button', { name: LABELS.finalizeLabel }))

      expect(finalize.submit).toHaveBeenCalledTimes(1)
    })

    it('disables the finalize button while the request is in flight', () => {
      renderSection({ finalize: { isPending: true, submit: vi.fn() } })

      expect(
        (screen.getByRole('button', { name: LABELS.finalizeLabel }) as HTMLButtonElement).disabled,
      ).toBe(true)
    })

    it('offers to start the conversation while there is no message yet', async () => {
      const user = userEvent.setup()
      const { chat } = renderSection()

      await user.click(screen.getByRole('button', { name: LABELS.chatStartLabel }))

      // 初回は利用者の発言なしで実績だけを送る。
      expect(chat.send).toHaveBeenCalledWith(null)
    })

    it('disables the start button while the request is in flight', () => {
      renderSection({
        chat: { isPending: true, wasTruncated: false, contextCategories: [], send: vi.fn() },
      })

      expect(
        (screen.getByRole('button', { name: LABELS.chatStartLabel }) as HTMLButtonElement).disabled,
      ).toBe(true)
    })

    it('replaces the start button with an input once the conversation has begun', async () => {
      const user = userEvent.setup()
      const { chat } = renderSection({ messages: [MESSAGE] })

      expect(screen.queryByRole('button', { name: LABELS.chatStartLabel })).toBe(null)
      await user.type(
        screen.getByPlaceholderText(t('dailyReport.chat.inputPlaceholder')),
        'follow-up',
      )
      await user.click(screen.getByRole('button', { name: t('dailyReport.chat.sendButton') }))

      expect(chat.send).toHaveBeenCalledWith('follow-up')
    })

    it('notifies when the prompt had to be truncated', () => {
      renderSection({
        messages: [MESSAGE],
        chat: { isPending: false, wasTruncated: true, contextCategories: [], send: vi.fn() },
      })

      expect(screen.getByText(t('dailyReport.chat.truncatedNotice'))).toBeTruthy()
    })

    it('shows a collapsed summary of what information was sent to the AI on the last exchange', () => {
      renderSection({
        messages: [MESSAGE],
        chat: {
          isPending: false,
          wasTruncated: false,
          contextCategories: ['GOAL_INFO', 'TODAY_RECORD'],
          send: vi.fn(),
        },
      })

      const summary = screen.getByText(t('dailyReport.chat.contextCategoriesSummary'))
      // 展開できる（折りたたみ）ことを検証する。プロンプト全文は表示しない前提のため、
      // 種別の一覧が<details>の中身として存在すること自体を確認すれば十分（仕様書該当追加分）。
      const details = summary.closest('details')
      expect(details?.open).toBe(false)
      expect(screen.getByText(t('dailyReport.chat.contextCategories.GOAL_INFO'))).toBeTruthy()
      expect(screen.getByText(t('dailyReport.chat.contextCategories.TODAY_RECORD'))).toBeTruthy()
    })

    it('shows nothing about the AI context before any exchange happens', () => {
      renderSection({ messages: [] })

      expect(
        screen.queryByText(t('dailyReport.chat.contextCategoriesSummary')),
      ).toBe(null)
    })

    it('always shows that nothing is sent outside this PC, even before the first exchange', () => {
      renderSection({ messages: [] })

      expect(screen.getByText(t('dailyReport.chat.privacyNotice'))).toBeTruthy()
    })

    it('shows a guidance notice instead of the chat when AI is not configured', async () => {
      mockAiConfigured(false)
      renderSection({ messages: [] })

      expect(
        await screen.findByText(t('aiUnconfigured.message')),
      ).toBeTruthy()
      expect(screen.queryByRole('button', { name: LABELS.chatStartLabel })).toBe(null)
      expect(screen.queryByText(t('dailyReport.chat.privacyNotice'))).toBe(null)
    })

    it('still shows the summary and finalize button when AI is not configured (recording keeps working)', async () => {
      mockAiConfigured(false)
      renderSection()

      await screen.findByText(t('aiUnconfigured.message'))
      expect(screen.getByText(EDITOR_MARKER)).toBeTruthy()
      expect(screen.getByRole('button', { name: LABELS.finalizeLabel })).toBeTruthy()
    })
  })

  describe('once the category is finalized', () => {
    it('shows the summary with the confirmed badge and hides the editor', () => {
      renderSection({ isReported: true })

      expect(screen.getByText(SUMMARY_MARKER)).toBeTruthy()
      expect(screen.queryByText(EDITOR_MARKER)).toBe(null)
      expect(screen.getByText(t('dailyReport.confirmedBadge'))).toBeTruthy()
    })

    it('hides the finalize button so the category cannot be finalized twice', () => {
      renderSection({ isReported: true })

      expect(screen.queryByRole('button', { name: LABELS.finalizeLabel })).toBe(null)
    })

    it('keeps the conversation read-only', () => {
      renderSection({ isReported: true, messages: [MESSAGE] })

      expect(screen.getByText(MESSAGE.content)).toBeTruthy()
      expect(screen.queryByRole('button', { name: LABELS.chatStartLabel })).toBe(null)
      expect(screen.queryByPlaceholderText(t('dailyReport.chat.inputPlaceholder'))).toBe(null)
    })
  })
})
