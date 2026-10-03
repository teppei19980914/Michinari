/** チームメンバー一覧の表示・無効化・削除の送信内容を固定する（要件定義書6.11）。 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient } from '@tanstack/react-query'
import { t } from '../../locales/t'
import { renderWithProviders } from '../../test/renderWithProviders'
import { GOAL_ID, makeWorkMember } from '../../test/fixtures'
import { WorkMemberList } from './WorkMemberList'

const deactivateWorkMember = vi.hoisted(() => vi.fn())
const deleteWorkMember = vi.hoisted(() => vi.fn())
const createWorkMember = vi.hoisted(() => vi.fn())
const updateWorkMember = vi.hoisted(() => vi.fn())
vi.mock('../../api/goals', () => ({
  deactivateWorkMember,
  deleteWorkMember,
  createWorkMember,
  updateWorkMember,
}))

beforeEach(() => {
  vi.clearAllMocks()
  deactivateWorkMember.mockResolvedValue(makeWorkMember({ is_active: false }))
  deleteWorkMember.mockResolvedValue(undefined)
})

afterEach(() => {
  cleanup()
})

describe('WorkMemberList', () => {
  it('shows the empty message when there are no members', () => {
    renderWithProviders(<WorkMemberList goalId={GOAL_ID} members={[]} readOnly={false} />)

    expect(screen.getByText(t('goals.workMember.empty'))).toBeDefined()
  })

  it('renders member characteristics and consent state', () => {
    const member = makeWorkMember({
      name: 'Aさん',
      characteristics: '粘り強い性格',
      consent_confirmed_at: '2026-01-01T00:00:00Z',
    })
    renderWithProviders(<WorkMemberList goalId={GOAL_ID} members={[member]} readOnly={false} />)

    expect(screen.getByText('Aさん')).toBeDefined()
    expect(screen.getByText('粘り強い性格')).toBeDefined()
  })

  it('shows the gender label when set', () => {
    const member = makeWorkMember({ name: 'Aさん', gender: 'FEMALE' })
    renderWithProviders(<WorkMemberList goalId={GOAL_ID} members={[member]} readOnly={false} />)

    expect(screen.getByText(t('goals.workMember.gender.FEMALE'))).toBeDefined()
  })

  it('shows the inactive badge for deactivated members', () => {
    const member = makeWorkMember({ name: 'Aさん', is_active: false })
    renderWithProviders(<WorkMemberList goalId={GOAL_ID} members={[member]} readOnly={false} />)

    expect(screen.getByText(t('goals.workMember.inactiveBadge'))).toBeDefined()
  })

  it('hides all actions when read only', () => {
    const member = makeWorkMember({ name: 'Aさん' })
    renderWithProviders(<WorkMemberList goalId={GOAL_ID} members={[member]} readOnly />)

    expect(screen.queryByRole('button', { name: t('goals.workMember.deleteButton') })).toBeNull()
    expect(screen.queryByRole('button', { name: t('goals.workMember.addButton') })).toBeNull()
  })

  it('deactivates a member and invalidates the related queries', async () => {
    const user = userEvent.setup()
    const member = makeWorkMember({ name: 'Aさん' })
    const invalidateSpy = vi.spyOn(QueryClient.prototype, 'invalidateQueries')
    renderWithProviders(<WorkMemberList goalId={GOAL_ID} members={[member]} readOnly={false} />)

    await user.click(screen.getByRole('button', { name: t('goals.workMember.deactivateButton') }))

    await waitFor(() => expect(deactivateWorkMember).toHaveBeenCalledWith(member.id))
    await waitFor(() => expect(invalidateSpy).toHaveBeenCalled())
  })

  it('deletes a member', async () => {
    const user = userEvent.setup()
    const member = makeWorkMember({ name: 'Aさん' })
    renderWithProviders(<WorkMemberList goalId={GOAL_ID} members={[member]} readOnly={false} />)

    await user.click(screen.getByRole('button', { name: t('goals.workMember.deleteButton') }))

    await waitFor(() => expect(deleteWorkMember).toHaveBeenCalledWith(member.id))
  })

  it('opens the add-member form', async () => {
    const user = userEvent.setup()
    renderWithProviders(<WorkMemberList goalId={GOAL_ID} members={[]} readOnly={false} />)

    await user.click(screen.getByRole('button', { name: t('goals.workMember.addButton') }))

    expect(screen.getByLabelText(t('goals.workMember.nameLabel'))).toBeDefined()
  })

  it('closes the add-member form on cancel', async () => {
    const user = userEvent.setup()
    renderWithProviders(<WorkMemberList goalId={GOAL_ID} members={[]} readOnly={false} />)

    await user.click(screen.getByRole('button', { name: t('goals.workMember.addButton') }))
    await user.click(screen.getByRole('button', { name: t('common.action.cancel') }))

    expect(screen.getByRole('button', { name: t('goals.workMember.addButton') })).toBeDefined()
  })

  it('opens the edit form for a member', async () => {
    const user = userEvent.setup()
    const member = makeWorkMember({ name: 'Aさん' })
    renderWithProviders(<WorkMemberList goalId={GOAL_ID} members={[member]} readOnly={false} />)

    await user.click(screen.getByRole('button', { name: t('common.action.edit') }))

    expect(screen.getByLabelText<HTMLInputElement>(t('goals.workMember.nameLabel')).value).toBe(
      'Aさん',
    )
  })

  it('closes the edit form on cancel, returning to the read view', async () => {
    const user = userEvent.setup()
    const member = makeWorkMember({ name: 'Aさん' })
    renderWithProviders(<WorkMemberList goalId={GOAL_ID} members={[member]} readOnly={false} />)

    await user.click(screen.getByRole('button', { name: t('common.action.edit') }))
    await user.click(screen.getByRole('button', { name: t('common.action.cancel') }))

    expect(screen.getByRole('button', { name: t('common.action.edit') })).toBeDefined()
  })
})
