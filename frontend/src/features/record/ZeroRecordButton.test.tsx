import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes } from 'react-router-dom'
import { renderWithProviders } from '../../test/renderWithProviders'
import { t } from '../../locales/t'
import * as recordsApi from '../../api/records'
import * as calendarApi from '../../api/calendar'
import { ZeroRecordButton, type ZeroRecordButtonProps } from './ZeroRecordButton'
import type { CategoryPresence } from './categoryCompletion'

vi.mock('../../api/records')
vi.mock('../../api/calendar')

const TARGET_DATE = '2026-09-17'
const DASHBOARD_MARKER = 'dashboard-page'

function buildRecord(overrides: Partial<recordsApi.DailyRecordRead> = {}): recordsApi.DailyRecordRead {
  return {
    record_date: TARGET_DATE,
    exam_record_state: null,
    reading_record_state: null,
    work_record_state: null,
    exam_reported_at: null,
    reading_reported_at: null,
    work_reported_at: null,
    diary_entries: [],
    study_logs: [],
    reading_logs: [],
    work_logs: [],
    comments: [],
    chat_messages: [],
    ...overrides,
  }
}

function renderButton(props: Partial<ZeroRecordButtonProps> = {}) {
  const presence: CategoryPresence = {
    hasExamCategory: true,
    hasReadingCategory: false,
    hasWorkCategory: false,
  }
  renderWithProviders(
    <Routes>
      <Route
        path="/report"
        element={
          <ZeroRecordButton
            targetDate={TARGET_DATE}
            categories={['EXAM']}
            presence={presence}
            {...props}
          />
        }
      />
      {/* ROUTES.dashboard は '/' のため、遷移確認用のマーカーはルートパスに置く。 */}
      <Route path="/" element={<p>{DASHBOARD_MARKER}</p>} />
    </Routes>,
    { initialEntries: ['/report'] },
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(calendarApi.getCalendar).mockResolvedValue([
    { target_date: TARGET_DATE, day_type: 'PLAN', record_state: null },
  ])
  vi.mocked(recordsApi.finalizeRecord).mockResolvedValue(buildRecord({ exam_record_state: 'REPORTED' }))
  vi.mocked(recordsApi.finalizeReadingRecord).mockResolvedValue(
    buildRecord({ reading_record_state: 'REPORTED' }),
  )
  vi.mocked(recordsApi.finalizeWorkRecord).mockResolvedValue(
    buildRecord({ work_record_state: 'REPORTED' }),
  )
})

afterEach(() => {
  cleanup()
})

describe('ZeroRecordButton', () => {
  it('renders nothing when there is no eligible category', () => {
    renderWithProviders(
      <ZeroRecordButton
        targetDate={TARGET_DATE}
        categories={[]}
        presence={{ hasExamCategory: false, hasReadingCategory: false, hasWorkCategory: false }}
      />,
    )
    expect(screen.queryByRole('button')).toBe(null)
  })

  it('does nothing until the confirmation is submitted', async () => {
    const user = userEvent.setup()
    renderButton()

    await user.click(screen.getByRole('button', { name: t('dailyReport.zeroRecord.button') }))
    expect(screen.getByText(t('dailyReport.zeroRecord.confirmBody'))).toBeTruthy()
    expect(recordsApi.finalizeRecord).not.toHaveBeenCalled()
  })

  it('closes the confirmation without submitting when cancelled', async () => {
    const user = userEvent.setup()
    renderButton()

    await user.click(screen.getByRole('button', { name: t('dailyReport.zeroRecord.button') }))
    await user.click(screen.getByRole('button', { name: t('dailyReport.zeroRecord.confirmCancel') }))

    expect(screen.queryByText(t('dailyReport.zeroRecord.confirmBody'))).toBe(null)
    expect(recordsApi.finalizeRecord).not.toHaveBeenCalled()
  })

  it('closes the confirmation without submitting when the modal close button is used', async () => {
    const user = userEvent.setup()
    renderButton()

    await user.click(screen.getByRole('button', { name: t('dailyReport.zeroRecord.button') }))
    await user.click(screen.getByRole('button', { name: 'close' }))

    expect(screen.queryByText(t('dailyReport.zeroRecord.confirmBody'))).toBe(null)
    expect(recordsApi.finalizeRecord).not.toHaveBeenCalled()
  })

  it('finalizes every eligible category with an empty payload and shows the plan-day message', async () => {
    const user = userEvent.setup()
    const presence: CategoryPresence = {
      hasExamCategory: true,
      hasReadingCategory: true,
      hasWorkCategory: false,
    }
    renderButton({ categories: ['EXAM', 'READING'], presence })

    await user.click(screen.getByRole('button', { name: t('dailyReport.zeroRecord.button') }))
    await user.click(screen.getByRole('button', { name: t('dailyReport.zeroRecord.confirmSubmit') }))

    await waitFor(() => expect(recordsApi.finalizeReadingRecord).toHaveBeenCalled())
    expect(recordsApi.finalizeRecord).toHaveBeenCalledWith(TARGET_DATE, {
      study_logs: [],
      diary_entries: [],
    })
    expect(recordsApi.finalizeReadingRecord).toHaveBeenCalledWith(TARGET_DATE, { reading_logs: [] })
    expect(recordsApi.finalizeWorkRecord).not.toHaveBeenCalled()
    expect(await screen.findByText(t('dailyReport.zeroRecord.planDayMessage'))).toBeTruthy()
  })

  it('shows the rest-day message on a BUFFER day', async () => {
    vi.mocked(calendarApi.getCalendar).mockResolvedValue([
      { target_date: TARGET_DATE, day_type: 'BUFFER', record_state: null },
    ])
    const user = userEvent.setup()
    renderButton()

    await user.click(screen.getByRole('button', { name: t('dailyReport.zeroRecord.button') }))
    await user.click(screen.getByRole('button', { name: t('dailyReport.zeroRecord.confirmSubmit') }))

    expect(await screen.findByText(t('dailyReport.zeroRecord.restDayMessage'))).toBeTruthy()
  })

  it('navigates to the dashboard once every active category is reported', async () => {
    const user = userEvent.setup()
    const presence: CategoryPresence = {
      hasExamCategory: true,
      hasReadingCategory: false,
      hasWorkCategory: false,
    }
    renderButton({ categories: ['EXAM'], presence })

    await user.click(screen.getByRole('button', { name: t('dailyReport.zeroRecord.button') }))
    await user.click(screen.getByRole('button', { name: t('dailyReport.zeroRecord.confirmSubmit') }))

    expect(await screen.findByText(DASHBOARD_MARKER)).toBeTruthy()
  })

  it('stays on the page when another active category is still unreported', async () => {
    const user = userEvent.setup()
    const presence: CategoryPresence = {
      hasExamCategory: true,
      hasReadingCategory: true,
      hasWorkCategory: false,
    }
    // 読書は進捗のみ登録済みのため対象外（categoriesにEXAMのみ）だが、presence上は
    // 読書もACTIVEなため全カテゴリ確定済みにはならない。
    renderButton({ categories: ['EXAM'], presence })

    await user.click(screen.getByRole('button', { name: t('dailyReport.zeroRecord.button') }))
    await user.click(screen.getByRole('button', { name: t('dailyReport.zeroRecord.confirmSubmit') }))

    await waitFor(() => expect(recordsApi.finalizeRecord).toHaveBeenCalled())
    expect(screen.queryByText(DASHBOARD_MARKER)).toBe(null)
  })
})
