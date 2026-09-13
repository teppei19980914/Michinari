/** 案件情報タブの送信内容と、案件の未登録／登録済み／編集中の切り替えを固定する（Phase 35）。
 *
 * 取引先呼称は任意項目のため、空欄を空文字ではなく `null` として送る必要がある。
 * 空文字のまま送ると「取引先なし」と区別できず、ナレッジエクスポートの概要欄が空欄化する
 * （Phase23で実際に起きた不具合と同じ経路）。 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { t } from '../../locales/t'
import { renderWithProviders } from '../../test/renderWithProviders'
import { GOAL_ID, makeGoalDetail, makeWorkAssignment } from '../../test/fixtures'
import { WorkAssignmentTab } from './WorkAssignmentTab'

const createWorkAssignment = vi.hoisted(() => vi.fn())
const updateWorkAssignment = vi.hoisted(() => vi.fn())
vi.mock('../../api/goals', () => ({ createWorkAssignment, updateWorkAssignment }))

const saveButton = () => screen.getByRole('button', { name: t('common.action.save') })
const editButton = () => screen.getByRole('button', { name: t('common.action.edit') })
const cancelButton = () => screen.getByRole('button', { name: t('common.action.cancel') })
const contentInput = () => screen.getByLabelText(t('goals.workAssignment.expectedContentLabel'))
const startDateInput = () =>
  screen.getByLabelText<HTMLInputElement>(t('goals.workAssignment.startDateLabel'))

const goalWithoutAssignment = () => makeGoalDetail({ category: 'WORK' })
const goalWithAssignment = (overrides = {}) =>
  makeGoalDetail({ category: 'WORK', work_assignment: makeWorkAssignment(overrides) })

beforeEach(() => {
  vi.clearAllMocks()
  createWorkAssignment.mockResolvedValue(makeWorkAssignment())
  updateWorkAssignment.mockResolvedValue(makeWorkAssignment())
})

afterEach(() => {
  cleanup()
})

describe('WorkAssignmentTab の表示', () => {
  it('shows the empty message when there is no assignment and the goal is read only', () => {
    renderWithProviders(<WorkAssignmentTab goal={goalWithoutAssignment()} readOnly />)

    expect(screen.getByText(t('goals.workAssignment.empty'))).toBeDefined()
  })

  it('offers the registration form when there is no assignment yet', () => {
    renderWithProviders(<WorkAssignmentTab goal={goalWithoutAssignment()} readOnly={false} />)

    expect(contentInput()).toBeDefined()
    // 登録前は取りやめる先がないためキャンセルは出さない。
    expect(screen.queryByRole('button', { name: t('common.action.cancel') })).toBeNull()
  })

  it('hides the client name line when there is none', () => {
    const { unmount } = renderWithProviders(
      <WorkAssignmentTab goal={goalWithAssignment()} readOnly />,
    )
    expect(screen.getByText('取引先A')).toBeDefined()

    unmount()
    renderWithProviders(
      <WorkAssignmentTab goal={goalWithAssignment({ client_name: null })} readOnly />,
    )

    expect(screen.queryByText('取引先A')).toBeNull()
  })

  it('falls back when the assignment has never been worked on', () => {
    renderWithProviders(
      <WorkAssignmentTab goal={goalWithAssignment({ last_work_date: null })} readOnly />,
    )

    expect(screen.getByText(t('goals.workAssignment.lastWorkDateUnavailable'))).toBeDefined()
  })

  it('states whether a recent monthly report exists', () => {
    const { unmount } = renderWithProviders(
      <WorkAssignmentTab goal={goalWithAssignment()} readOnly />,
    )
    expect(screen.getByText(t('common.yes'))).toBeDefined()

    unmount()
    renderWithProviders(
      <WorkAssignmentTab
        goal={goalWithAssignment({ has_recent_monthly_report: false })}
        readOnly
      />,
    )

    expect(
      screen.getByText(t('goals.workAssignment.hasRecentMonthlyReportNone')),
    ).toBeDefined()
  })

  it('hides editing when read only', () => {
    renderWithProviders(<WorkAssignmentTab goal={goalWithAssignment()} readOnly />)

    expect(screen.queryByRole('button', { name: t('common.action.edit') })).toBeNull()
  })
})

describe('WorkAssignmentTab の送信内容', () => {
  it('creates the assignment and sends null for an empty client name', async () => {
    const user = userEvent.setup()
    renderWithProviders(<WorkAssignmentTab goal={goalWithoutAssignment()} readOnly={false} />)

    await user.type(contentInput(), '成果の説明')
    fireEvent.change(startDateInput(), { target: { value: '2026-09-01' } })
    await user.click(saveButton())

    await waitFor(() => expect(createWorkAssignment).toHaveBeenCalledOnce())
    expect(createWorkAssignment).toHaveBeenCalledWith(GOAL_ID, {
      // 任意項目の空欄は空文字ではなく未設定として送る。
      client_name: null,
      expected_content: '成果の説明',
      start_date: '2026-09-01',
    })
  })

  it('keeps the client name when it is entered', async () => {
    const user = userEvent.setup()
    renderWithProviders(<WorkAssignmentTab goal={goalWithoutAssignment()} readOnly={false} />)

    await user.type(screen.getByLabelText(t('goals.workAssignment.clientNameLabel')), '取引先B')
    await user.type(contentInput(), '成果の説明')
    fireEvent.change(startDateInput(), { target: { value: '2026-09-01' } })
    await user.click(saveButton())

    await waitFor(() => expect(createWorkAssignment).toHaveBeenCalledOnce())
    expect(createWorkAssignment.mock.calls[0][1]).toMatchObject({ client_name: '取引先B' })
  })

  it('updates the existing assignment instead of creating a new one', async () => {
    const user = userEvent.setup()
    renderWithProviders(<WorkAssignmentTab goal={goalWithAssignment()} readOnly={false} />)

    await user.click(editButton())
    await user.click(saveButton())

    await waitFor(() => expect(updateWorkAssignment).toHaveBeenCalledOnce())
    // 案件は1目標1件のため、更新でも案件IDではなく目標IDを渡す。
    expect(updateWorkAssignment.mock.calls[0][0]).toBe(GOAL_ID)
    expect(createWorkAssignment).not.toHaveBeenCalled()
  })

  it('leaves the edit form without sending anything on cancel', async () => {
    const user = userEvent.setup()
    renderWithProviders(<WorkAssignmentTab goal={goalWithAssignment()} readOnly={false} />)

    await user.click(editButton())
    await user.click(cancelButton())

    expect(updateWorkAssignment).not.toHaveBeenCalled()
    expect(editButton()).toBeDefined()
  })
})
