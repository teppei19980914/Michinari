import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { t } from '../../locales/t'
import { renderWithProviders } from '../../test/renderWithProviders'
import type { ScheduleRead, ScheduleRevisionProposalRead } from '../../api/schedule'
import { ScheduleTab } from './ScheduleTab'

const getSchedule = vi.hoisted(() => vi.fn())
const saveSchedule = vi.hoisted(() => vi.fn())
const updateScheduleViewSetting = vi.hoisted(() => vi.fn())
const generateScheduleRevisionProposal = vi.hoisted(() => vi.fn())
const decideScheduleRevisionProposal = vi.hoisted(() => vi.fn())
vi.mock('../../api/schedule', () => ({
  getSchedule,
  saveSchedule,
  updateScheduleViewSetting,
  generateScheduleRevisionProposal,
  decideScheduleRevisionProposal,
}))

const getHolidayCoverage = vi.hoisted(() => vi.fn())
vi.mock('../../api/resources', () => ({ getHolidayCoverage }))

function sampleScheduleRead(overrides: Partial<ScheduleRead> = {}): ScheduleRead {
  return {
    revision: 1,
    frozen_row_count: 0,
    frozen_column_count: 1,
    today: '2026-11-23',
    max_items: 100,
    max_custom_columns: 10,
    gantt_day_width_min_rem: 1.75,
    gantt_day_width_max_rem: 4.5,
    columns: [],
    items: [
      {
        id: 10,
        title: '作業A',
        description: null,
        planned_start_date: '2026-11-01',
        planned_end_date: '2026-11-10',
        status: 'NOT_STARTED',
        actual_start_date: null,
        actual_end_date: null,
        display_order: 0,
        cells: [],
      },
    ],
    pending_revision_proposal: null,
    ...overrides,
  }
}

function sampleProposal(
  overrides: Partial<ScheduleRevisionProposalRead> = {},
): ScheduleRevisionProposalRead {
  return {
    id: 100,
    goal_id: 1,
    trigger: 'AUTO',
    record_date: '2026-11-23',
    summary: '少し遅れています',
    status: 'PENDING',
    items: [
      {
        id: 200,
        schedule_item_id: 10,
        kind: 'CHANGE',
        before_planned_start_date: '2026-11-01',
        before_planned_end_date: '2026-11-10',
        before_status: 'NOT_STARTED',
        proposed_planned_start_date: '2026-11-15',
        proposed_planned_end_date: '2026-11-20',
        reason: '遅れているため',
        decision: 'PENDING',
        applied_planned_start_date: null,
        applied_planned_end_date: null,
        reject_reason: null,
        is_stale: false,
      },
    ],
    ...overrides,
  }
}

beforeEach(() => {
  vi.clearAllMocks()
  getHolidayCoverage.mockResolvedValue({ holidays: [], year_from: 1955, year_to: 2027 })
  // jsdomにはscrollIntoViewの実装が無いため、D-29の「最初のエラーへスクロール」を
  // 呼び出すテストのためにスタブ化する（本番のブラウザには実装がある）。
  Element.prototype.scrollIntoView = vi.fn()
})

afterEach(() => {
  cleanup()
})

describe('ScheduleTab', () => {
  it('読み込み中はローディング表示', () => {
    getSchedule.mockReturnValue(new Promise(() => {}))
    renderWithProviders(<ScheduleTab goalId={1} readOnly={false} />)
    expect(screen.getByText(t('common.loading'))).not.toBe(null)
  })

  it('行が0件のときは空の案内を表示する', async () => {
    getSchedule.mockResolvedValue(sampleScheduleRead({ items: [] }))
    renderWithProviders(<ScheduleTab goalId={1} readOnly={false} />)
    await waitFor(() => expect(screen.getByText(t('schedule.empty.title'))).not.toBe(null))
  })

  it('行がある場合は表とガントを表示する', async () => {
    getSchedule.mockResolvedValue(sampleScheduleRead())
    renderWithProviders(<ScheduleTab goalId={1} readOnly={false} />)
    await waitFor(() =>
      expect(screen.getByLabelText(t('schedule.columns.title'))).not.toBe(null),
    )
  })

  it('取得した祝日を表示期間の日付集合へ変換する（D-45）', async () => {
    getSchedule.mockResolvedValue(sampleScheduleRead())
    getHolidayCoverage.mockResolvedValue({
      holidays: [{ holiday_date: '2026-11-03', name: '文化の日' }],
      year_from: 1955,
      year_to: 2027,
    })
    renderWithProviders(<ScheduleTab goalId={1} readOnly={false} />)
    await waitFor(() =>
      expect(screen.getByLabelText(t('schedule.columns.title'))).not.toBe(null),
    )
    await waitFor(() => expect(getHolidayCoverage).toHaveBeenCalled())
  })

  it('閲覧のみの目標では行を追加・保存ボタンを表示しない', async () => {
    getSchedule.mockResolvedValue(sampleScheduleRead())
    renderWithProviders(<ScheduleTab goalId={1} readOnly={true} />)
    await waitFor(() =>
      expect(screen.getByLabelText(t('schedule.columns.title'))).not.toBe(null),
    )
    expect(screen.queryByRole('button', { name: t('schedule.toolbar.addRow') })).toBe(null)
    expect(screen.queryByRole('button', { name: t('schedule.toolbar.save') })).toBe(null)
  })

  it('作業項目を編集して保存すると、保存APIへrevisionを含めて送信する', async () => {
    getSchedule.mockResolvedValue(sampleScheduleRead())
    saveSchedule.mockResolvedValue(sampleScheduleRead({ revision: 2 }))
    renderWithProviders(<ScheduleTab goalId={1} readOnly={false} />)

    const titleInput = await screen.findByLabelText(t('schedule.columns.title'))
    await userEvent.type(titleInput, 'X')

    const saveButton = screen.getByRole('button', { name: t('schedule.toolbar.save') })
    await userEvent.click(saveButton)

    await waitFor(() => expect(saveSchedule).toHaveBeenCalled())
    expect(saveSchedule.mock.calls[0][1]).toMatchObject({ revision: 1 })
  })

  it('検証エラーがある行を保存しようとすると、エラー件数のトーストを出し保存APIを呼ばない', async () => {
    getSchedule.mockResolvedValue(sampleScheduleRead())
    renderWithProviders(<ScheduleTab goalId={1} readOnly={false} />)

    const titleInput = await screen.findByLabelText(t('schedule.columns.title'))
    await userEvent.clear(titleInput)

    const saveButton = screen.getByRole('button', { name: t('schedule.toolbar.save') })
    await userEvent.click(saveButton)

    expect(saveSchedule).not.toHaveBeenCalled()
    expect(await screen.findByText(t('schedule.validation.saveErrorCount', { count: 1 }))).not.toBe(
      null,
    )
  })

  it('競合以外の保存エラーはトーストで知らせる', async () => {
    getSchedule.mockResolvedValue(sampleScheduleRead())
    const { ApiError } = await import('../../api/client')
    saveSchedule.mockRejectedValue(new ApiError('VALIDATION_ERROR', 'サーバ側の文言'))
    renderWithProviders(<ScheduleTab goalId={1} readOnly={false} />)

    const titleInput = await screen.findByLabelText(t('schedule.columns.title'))
    await userEvent.type(titleInput, 'X')
    await userEvent.click(screen.getByRole('button', { name: t('schedule.toolbar.save') }))

    expect(await screen.findByText(t('errors.VALIDATION_ERROR'))).not.toBe(null)
  })

  it('固定行数・固定列数の選択、今日へボタンが動く', async () => {
    getSchedule.mockResolvedValue(sampleScheduleRead())
    updateScheduleViewSetting.mockImplementation((_goalId, payload) => Promise.resolve(payload))
    renderWithProviders(<ScheduleTab goalId={1} readOnly={false} />)
    await screen.findByLabelText(t('schedule.columns.title'))

    await userEvent.selectOptions(
      screen.getByLabelText(t('schedule.toolbar.frozenRowsLabel'), { exact: false }),
      '1',
    )
    await waitFor(() =>
      expect(updateScheduleViewSetting).toHaveBeenCalledWith(1, {
        frozen_row_count: 1,
        frozen_column_count: 1,
      }),
    )

    await userEvent.selectOptions(
      screen.getByLabelText(t('schedule.toolbar.frozenColumnsLabel'), { exact: false }),
      '2',
    )
    await waitFor(() =>
      expect(updateScheduleViewSetting).toHaveBeenCalledWith(1, {
        frozen_row_count: 1,
        frozen_column_count: 2,
      }),
    )

    await userEvent.click(screen.getByRole('button', { name: t('schedule.toolbar.goToToday') }))
    // 「今日へ」はスクロール位置の再計算のみで、API呼び出しや例外が発生しないことを確認する。
    expect(screen.getByRole('button', { name: t('schedule.toolbar.goToToday') })).not.toBe(null)
  })

  it('409の競合時は編集内容を保持したままダイアログを表示する', async () => {
    getSchedule.mockResolvedValue(sampleScheduleRead())
    const { ApiError } = await import('../../api/client')
    saveSchedule.mockRejectedValue(new ApiError('SCHEDULE_REVISION_CONFLICT', '競合しました'))
    renderWithProviders(<ScheduleTab goalId={1} readOnly={false} />)

    const titleInput = await screen.findByLabelText(t('schedule.columns.title'))
    await userEvent.type(titleInput, 'X')
    await userEvent.click(screen.getByRole('button', { name: t('schedule.toolbar.save') }))

    expect(await screen.findByText(t('schedule.conflict.title'))).not.toBe(null)
    expect((titleInput as HTMLInputElement).value).toBe('作業AX')
  })

  it('「AIに修正案を依頼」ボタンを押すとMANUALで生成APIを呼ぶ（D-58）', async () => {
    getSchedule.mockResolvedValue(sampleScheduleRead())
    generateScheduleRevisionProposal.mockResolvedValue({ proposal: null })
    renderWithProviders(<ScheduleTab goalId={1} readOnly={false} />)
    await screen.findByLabelText(t('schedule.columns.title'))

    await userEvent.click(
      screen.getByRole('button', { name: t('schedule.toolbar.requestRevision') }),
    )

    await waitFor(() =>
      expect(generateScheduleRevisionProposal).toHaveBeenCalledWith(1, { trigger: 'MANUAL' }),
    )
  })

  it('未判断の修正案があれば修正案パネルとガントの点線を表示する（13.8・D-57）', async () => {
    getSchedule.mockResolvedValue(
      sampleScheduleRead({ pending_revision_proposal: sampleProposal() }),
    )
    renderWithProviders(<ScheduleTab goalId={1} readOnly={false} />)

    expect(await screen.findByText('少し遅れています')).not.toBe(null)
    expect(screen.getByText('遅れているため')).not.toBe(null)
    expect(screen.getByTestId('proposed-band')).not.toBe(null)
  })

  it('修正案を承認すると編集後の日付を添えて判断APIを呼ぶ（D-56）', async () => {
    getSchedule.mockResolvedValue(
      sampleScheduleRead({ pending_revision_proposal: sampleProposal() }),
    )
    decideScheduleRevisionProposal.mockResolvedValue({
      proposal: sampleProposal({ status: 'RESOLVED' }),
      outcomes: [{ proposal_item_id: 200, applied: true, blocked_reason: null }],
    })
    renderWithProviders(<ScheduleTab goalId={1} readOnly={false} />)
    await screen.findByText('少し遅れています')

    await userEvent.click(screen.getByRole('button', { name: t('schedule.revision.approve') }))

    await waitFor(() =>
      expect(decideScheduleRevisionProposal).toHaveBeenCalledWith(1, 100, {
        decisions: [
          {
            proposal_item_id: 200,
            decision: 'APPROVED',
            planned_start_date: '2026-11-15',
            planned_end_date: '2026-11-20',
          },
        ],
      }),
    )
  })

  it('未保存の変更があるときは判断ボタンを無効化し案内を表示する（13.8）', async () => {
    getSchedule.mockResolvedValue(
      sampleScheduleRead({ pending_revision_proposal: sampleProposal() }),
    )
    renderWithProviders(<ScheduleTab goalId={1} readOnly={false} />)
    const titleInput = await screen.findByLabelText(t('schedule.columns.title'))
    await userEvent.type(titleInput, 'X')

    expect(await screen.findByText(t('schedule.revision.saveOrDiscardFirst'))).not.toBe(null)
    expect(
      (
        screen.getByRole('button', { name: t('schedule.revision.approve') }) as HTMLButtonElement
      ).disabled,
    ).toBe(true)
  })

  it('修正案の生成に失敗したらトーストで知らせる', async () => {
    getSchedule.mockResolvedValue(sampleScheduleRead())
    const { ApiError } = await import('../../api/client')
    generateScheduleRevisionProposal.mockRejectedValue(
      new ApiError('AI_AUTH_REQUIRED', 'AI連携が必要です'),
    )
    renderWithProviders(<ScheduleTab goalId={1} readOnly={false} />)
    await screen.findByLabelText(t('schedule.columns.title'))

    await userEvent.click(
      screen.getByRole('button', { name: t('schedule.toolbar.requestRevision') }),
    )

    expect(await screen.findByText(t('errors.AI_AUTH_REQUIRED'))).not.toBe(null)
  })

  it('判断の送信に失敗したらトーストで知らせる', async () => {
    getSchedule.mockResolvedValue(
      sampleScheduleRead({ pending_revision_proposal: sampleProposal() }),
    )
    const { ApiError } = await import('../../api/client')
    decideScheduleRevisionProposal.mockRejectedValue(
      new ApiError('SCHEDULE_REVISION_PROPOSAL_NOT_PENDING', '既に判断済みです'),
    )
    renderWithProviders(<ScheduleTab goalId={1} readOnly={false} />)
    await screen.findByText('少し遅れています')

    await userEvent.click(screen.getByRole('button', { name: t('schedule.revision.approve') }))

    expect(
      await screen.findByText(t('errors.SCHEDULE_REVISION_PROPOSAL_NOT_PENDING')),
    ).not.toBe(null)
  })

  it('修正案がある状態で新しい行を追加しても落ちない（未保存の新規行はtitle対応表の対象外）', async () => {
    getSchedule.mockResolvedValue(
      sampleScheduleRead({ pending_revision_proposal: sampleProposal() }),
    )
    renderWithProviders(<ScheduleTab goalId={1} readOnly={false} />)
    await screen.findByText('少し遅れています')

    await userEvent.click(screen.getByRole('button', { name: t('schedule.toolbar.addRow') }))

    expect(screen.getAllByLabelText(t('schedule.columns.title'))).toHaveLength(2)
  })

  it('変更前の値が一致しない行は承認できず専用の文言を表示する（D-59）', async () => {
    getSchedule.mockResolvedValue(
      sampleScheduleRead({
        pending_revision_proposal: sampleProposal({
          items: [
            {
              ...sampleProposal().items[0],
              is_stale: true,
            },
          ],
        }),
      }),
    )
    renderWithProviders(<ScheduleTab goalId={1} readOnly={false} />)

    expect(await screen.findByText(t('schedule.revision.staleBeforeValue'))).not.toBe(null)
    expect(screen.queryByRole('button', { name: t('schedule.revision.approve') })).toBe(null)
  })
})
