/** 3カテゴリ（資格試験・読書・仕事）で共有するセクション構成の振る舞いを固定する。
 *
 * 従来この出し分けは DailyReportPage 内に3回書かれていた。1箇所へ集約したことで、ここが
 * 壊れると3カテゴリすべてが同時に壊れるため、確定済み/未確定の切り替えと対話の開始→送信の
 * 遷移を直接検証する（vite.config.ts の「押した結果まで含めて守りたいもの」に該当）。 */
import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { t } from '../../locales/t'
import type { ChatMessageRead } from '../../api/records'
import { CategoryReportSection, type CategoryReportSectionProps } from './CategoryReportSection'

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

function renderSection(overrides: Partial<CategoryReportSectionProps> = {}) {
  const chat = { isPending: false, wasTruncated: false, send: vi.fn() }
  const finalize = { isPending: false, submit: vi.fn() }
  render(
    <CategoryReportSection
      labels={LABELS}
      isReported={false}
      summary={<p>{SUMMARY_MARKER}</p>}
      editor={<p>{EDITOR_MARKER}</p>}
      messages={[]}
      chat={chat}
      finalize={finalize}
      {...overrides}
    />,
  )
  return { chat, finalize }
}

afterEach(() => {
  cleanup()
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
      renderSection({ chat: { isPending: true, wasTruncated: false, send: vi.fn() } })

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
        chat: { isPending: false, wasTruncated: true, send: vi.fn() },
      })

      expect(screen.getByText(t('dailyReport.chat.truncatedNotice'))).toBeTruthy()
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
