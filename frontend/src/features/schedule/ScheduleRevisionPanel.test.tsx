import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { t } from '../../locales/t'
import type { ScheduleRevisionProposalItemRead, ScheduleRevisionProposalRead } from '../../api/schedule'
import { ScheduleRevisionPanel } from './ScheduleRevisionPanel'
import type { EditedDates } from './useScheduleRevisionEditedDates'

function changeItem(overrides: Partial<ScheduleRevisionProposalItemRead> = {}): ScheduleRevisionProposalItemRead {
  return {
    id: 1,
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
    ...overrides,
  }
}

function warningItem(
  overrides: Partial<ScheduleRevisionProposalItemRead> = {},
): ScheduleRevisionProposalItemRead {
  return {
    ...changeItem(),
    id: 2,
    schedule_item_id: 20,
    kind: 'WARNING',
    proposed_planned_start_date: null,
    proposed_planned_end_date: null,
    reason: '期限内に収まりません',
    ...overrides,
  }
}

function proposal(overrides: Partial<ScheduleRevisionProposalRead> = {}): ScheduleRevisionProposalRead {
  return {
    id: 100,
    goal_id: 1,
    trigger: 'AUTO',
    record_date: '2026-11-23',
    summary: null,
    status: 'PENDING',
    items: [],
    ...overrides,
  }
}

function datesFor(item: ScheduleRevisionProposalItemRead): EditedDates {
  return {
    start: item.proposed_planned_start_date ?? '',
    end: item.proposed_planned_end_date ?? '',
  }
}

afterEach(() => cleanup())

describe('ScheduleRevisionPanel', () => {
  it('未判断の行が無ければ何も表示しない', () => {
    const { container } = render(
      <ScheduleRevisionPanel
        proposal={proposal({ items: [changeItem({ decision: 'APPROVED' })] })}
        itemTitleById={{}}
        canDecide={true}
        isDeciding={false}
        datesFor={datesFor}
        setDates={vi.fn()}
        onDecide={vi.fn()}
      />,
    )
    expect(container.firstChild).toBe(null)
  })

  it('変更行・注意行・総評を表示する', () => {
    render(
      <ScheduleRevisionPanel
        proposal={proposal({ summary: '全体的に遅れています', items: [changeItem(), warningItem()] })}
        itemTitleById={{ 10: '作業A', 20: '作業B' }}
        canDecide={true}
        isDeciding={false}
        datesFor={datesFor}
        setDates={vi.fn()}
        onDecide={vi.fn()}
      />,
    )
    expect(screen.getByText('全体的に遅れています')).not.toBe(null)
    expect(screen.getByText('作業A')).not.toBe(null)
    expect(screen.getByText('作業B')).not.toBe(null)
  })

  it('承認ボタンは編集後の日付を添えてonDecideを呼ぶ（D-56）', async () => {
    const onDecide = vi.fn()
    render(
      <ScheduleRevisionPanel
        proposal={proposal({ items: [changeItem()] })}
        itemTitleById={{ 10: '作業A' }}
        canDecide={true}
        isDeciding={false}
        datesFor={() => ({ start: '2026-11-16', end: '2026-11-21' })}
        setDates={vi.fn()}
        onDecide={onDecide}
      />,
    )

    await userEvent.click(screen.getByRole('button', { name: t('schedule.revision.approve') }))

    expect(onDecide).toHaveBeenCalledWith([
      {
        proposal_item_id: 1,
        decision: 'APPROVED',
        planned_start_date: '2026-11-16',
        planned_end_date: '2026-11-21',
      },
    ])
  })

  it('却下ボタンは入力した理由を添えてonDecideを呼ぶ', async () => {
    const onDecide = vi.fn()
    render(
      <ScheduleRevisionPanel
        proposal={proposal({ items: [changeItem()] })}
        itemTitleById={{ 10: '作業A' }}
        canDecide={true}
        isDeciding={false}
        datesFor={datesFor}
        setDates={vi.fn()}
        onDecide={onDecide}
      />,
    )

    await userEvent.type(
      screen.getByPlaceholderText(t('schedule.revision.rejectReasonPlaceholder')),
      'まだ早い',
    )
    await userEvent.click(screen.getByRole('button', { name: t('schedule.revision.reject') }))

    expect(onDecide).toHaveBeenCalledWith([
      { proposal_item_id: 1, decision: 'REJECTED', reject_reason: 'まだ早い' },
    ])
  })

  it('却下理由が空のときはnullを送る', async () => {
    const onDecide = vi.fn()
    render(
      <ScheduleRevisionPanel
        proposal={proposal({ items: [changeItem()] })}
        itemTitleById={{ 10: '作業A' }}
        canDecide={true}
        isDeciding={false}
        datesFor={datesFor}
        setDates={vi.fn()}
        onDecide={onDecide}
      />,
    )

    await userEvent.click(screen.getByRole('button', { name: t('schedule.revision.reject') }))

    expect(onDecide).toHaveBeenCalledWith([
      { proposal_item_id: 1, decision: 'REJECTED', reject_reason: null },
    ])
  })

  it('確認しましたボタンはACKNOWLEDGEDでonDecideを呼ぶ', async () => {
    const onDecide = vi.fn()
    render(
      <ScheduleRevisionPanel
        proposal={proposal({ items: [warningItem()] })}
        itemTitleById={{ 20: '作業B' }}
        canDecide={true}
        isDeciding={false}
        datesFor={datesFor}
        setDates={vi.fn()}
        onDecide={onDecide}
      />,
    )

    await userEvent.click(screen.getByRole('button', { name: t('schedule.revision.acknowledge') }))

    expect(onDecide).toHaveBeenCalledWith([{ proposal_item_id: 2, decision: 'ACKNOWLEDGED' }])
  })

  it('すべて承認はstale行を除いた全変更行をまとめて送る', async () => {
    const onDecide = vi.fn()
    render(
      <ScheduleRevisionPanel
        proposal={proposal({
          items: [changeItem({ id: 1 }), changeItem({ id: 3, is_stale: true })],
        })}
        itemTitleById={{ 10: '作業A' }}
        canDecide={true}
        isDeciding={false}
        datesFor={datesFor}
        setDates={vi.fn()}
        onDecide={onDecide}
      />,
    )

    await userEvent.click(screen.getByRole('button', { name: t('schedule.revision.approveAll') }))

    expect(onDecide).toHaveBeenCalledWith([
      {
        proposal_item_id: 1,
        decision: 'APPROVED',
        planned_start_date: '2026-11-15',
        planned_end_date: '2026-11-20',
      },
    ])
  })

  it('すべて却下はstale行を除いた全変更行をまとめて送る', async () => {
    const onDecide = vi.fn()
    render(
      <ScheduleRevisionPanel
        proposal={proposal({
          items: [changeItem({ id: 1 }), changeItem({ id: 3, is_stale: true })],
        })}
        itemTitleById={{ 10: '作業A' }}
        canDecide={true}
        isDeciding={false}
        datesFor={datesFor}
        setDates={vi.fn()}
        onDecide={onDecide}
      />,
    )

    await userEvent.click(screen.getByRole('button', { name: t('schedule.revision.rejectAll') }))

    expect(onDecide).toHaveBeenCalledWith([
      { proposal_item_id: 1, decision: 'REJECTED', reject_reason: null },
    ])
  })

  it('対象がすべてstaleのときはすべて承認・すべて却下を押してもonDecideを呼ばない', async () => {
    const onDecide = vi.fn()
    render(
      <ScheduleRevisionPanel
        proposal={proposal({ items: [changeItem({ is_stale: true })] })}
        itemTitleById={{ 10: '作業A' }}
        canDecide={true}
        isDeciding={false}
        datesFor={datesFor}
        setDates={vi.fn()}
        onDecide={onDecide}
      />,
    )

    await userEvent.click(screen.getByRole('button', { name: t('schedule.revision.approveAll') }))
    await userEvent.click(screen.getByRole('button', { name: t('schedule.revision.rejectAll') }))

    expect(onDecide).not.toHaveBeenCalled()
  })

  it('canDecideがfalseのときは案内を表示しすべてのボタンを無効化する', () => {
    render(
      <ScheduleRevisionPanel
        proposal={proposal({ items: [changeItem(), warningItem()] })}
        itemTitleById={{ 10: '作業A', 20: '作業B' }}
        canDecide={false}
        isDeciding={false}
        datesFor={datesFor}
        setDates={vi.fn()}
        onDecide={vi.fn()}
      />,
    )

    expect(screen.getByText(t('schedule.revision.saveOrDiscardFirst'))).not.toBe(null)
    expect(
      (screen.getByRole('button', { name: t('schedule.revision.approve') }) as HTMLButtonElement)
        .disabled,
    ).toBe(true)
    expect(
      (
        screen.getByRole('button', {
          name: t('schedule.revision.acknowledge'),
        }) as HTMLButtonElement
      ).disabled,
    ).toBe(true)
  })

  it('開始日・終了日を入力し直すとどちらもsetDatesが呼ばれる（D-56）', async () => {
    const setDates = vi.fn()
    render(
      <ScheduleRevisionPanel
        proposal={proposal({ items: [changeItem()] })}
        itemTitleById={{ 10: '作業A' }}
        canDecide={true}
        isDeciding={false}
        datesFor={datesFor}
        setDates={setDates}
        onDecide={vi.fn()}
      />,
    )

    const startInput = screen.getByLabelText(t('schedule.revision.proposedStartDate'))
    await userEvent.clear(startInput)
    await userEvent.type(startInput, '2026-11-18')
    const endInput = screen.getByLabelText(t('schedule.revision.proposedEndDate'))
    await userEvent.clear(endInput)
    await userEvent.type(endInput, '2026-11-22')

    expect(setDates).toHaveBeenCalled()
  })

  it('ブロックされた行は理由を表示するがボタンは無効化しない（修正1）', async () => {
    const onDecide = vi.fn()
    render(
      <ScheduleRevisionPanel
        proposal={proposal({ items: [changeItem({ id: 1 })] })}
        itemTitleById={{ 10: '作業A' }}
        canDecide={true}
        isDeciding={false}
        datesFor={datesFor}
        setDates={vi.fn()}
        onDecide={onDecide}
        blockedReasonFor={(itemId) => (itemId === 1 ? 'INVALID_PLANNED_DATE' : null)}
      />,
    )

    expect(screen.getByText(t('schedule.revision.invalidPlannedDate'))).not.toBe(null)
    const approveButton = screen.getByRole('button', {
      name: t('schedule.revision.approve'),
    }) as HTMLButtonElement
    expect(approveButton.disabled).toBe(false)

    await userEvent.click(approveButton)

    expect(onDecide).toHaveBeenCalled()
  })

  it('ブロックされた行は「すべて承認」の対象から除く（修正1）', async () => {
    const onDecide = vi.fn()
    render(
      <ScheduleRevisionPanel
        proposal={proposal({
          items: [changeItem({ id: 1 }), changeItem({ id: 3 })],
        })}
        itemTitleById={{ 10: '作業A' }}
        canDecide={true}
        isDeciding={false}
        datesFor={datesFor}
        setDates={vi.fn()}
        onDecide={onDecide}
        blockedReasonFor={(itemId) => (itemId === 3 ? 'INVALID_PLANNED_DATE' : null)}
      />,
    )

    await userEvent.click(screen.getByRole('button', { name: t('schedule.revision.approveAll') }))

    expect(onDecide).toHaveBeenCalledWith([
      {
        proposal_item_id: 1,
        decision: 'APPROVED',
        planned_start_date: '2026-11-15',
        planned_end_date: '2026-11-20',
      },
    ])
  })

  it('readOnly時は承認・却下・確認のボタンを一切表示しない（軽微な修正1）', () => {
    render(
      <ScheduleRevisionPanel
        proposal={proposal({ summary: '全体的に遅れています', items: [changeItem(), warningItem()] })}
        itemTitleById={{ 10: '作業A', 20: '作業B' }}
        canDecide={true}
        isDeciding={false}
        readOnly={true}
        datesFor={datesFor}
        setDates={vi.fn()}
        onDecide={vi.fn()}
      />,
    )

    expect(screen.getByText('全体的に遅れています')).not.toBe(null)
    expect(screen.getByText('遅れているため')).not.toBe(null)
    expect(screen.queryByRole('button', { name: t('schedule.revision.approve') })).toBe(null)
    expect(screen.queryByRole('button', { name: t('schedule.revision.reject') })).toBe(null)
    expect(screen.queryByRole('button', { name: t('schedule.revision.approveAll') })).toBe(null)
    expect(screen.queryByRole('button', { name: t('schedule.revision.rejectAll') })).toBe(null)
    expect(screen.queryByRole('button', { name: t('schedule.revision.acknowledge') })).toBe(null)
  })

  it('作業項目名が見つからない行は空文字で表示する（データ不整合に対する防御）', () => {
    render(
      <ScheduleRevisionPanel
        proposal={proposal({ items: [changeItem(), warningItem()] })}
        itemTitleById={{}}
        canDecide={true}
        isDeciding={false}
        datesFor={datesFor}
        setDates={vi.fn()}
        onDecide={vi.fn()}
      />,
    )

    expect(screen.getByText('遅れているため')).not.toBe(null)
    expect(screen.getByText('期限内に収まりません')).not.toBe(null)
  })
})
