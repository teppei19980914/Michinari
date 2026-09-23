/** チームメンバーフォームの同意ゲート・送信内容を固定する（要件定義書6.11）。
 *
 * characteristicsを保存する際は必ずconsent_confirmed=trueを送る必要がある
 * （サーバ側でも強制、work_member_service._apply_characteristics）。フォーム側は
 * 内容を変更するたびにチェック状態をリセットする。 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { t } from '../../locales/t'
import { renderWithProviders } from '../../test/renderWithProviders'
import { GOAL_ID, makeWorkMember } from '../../test/fixtures'
import { WorkMemberForm } from './WorkMemberForm'

const createWorkMember = vi.hoisted(() => vi.fn())
const updateWorkMember = vi.hoisted(() => vi.fn())
vi.mock('../../api/goals', () => ({ createWorkMember, updateWorkMember }))

const nameInput = () => screen.getByLabelText(t('goals.workMember.nameLabel'))
const characteristicsInput = () =>
  screen.getByLabelText(t('goals.workMember.characteristicsLabel'))
const saveButton = () => screen.getByRole('button', { name: t('common.action.save') })
const consentCheckbox = () =>
  screen.getByRole('checkbox', { name: new RegExp(t('goals.workMember.consentCheckbox')) })

beforeEach(() => {
  vi.clearAllMocks()
  createWorkMember.mockResolvedValue(makeWorkMember())
  updateWorkMember.mockResolvedValue(makeWorkMember())
})

afterEach(() => {
  cleanup()
})

describe('WorkMemberForm', () => {
  it('does not show the consent checkbox while characteristics is empty', () => {
    renderWithProviders(<WorkMemberForm goalId={GOAL_ID} onDone={vi.fn()} />)

    expect(
      screen.queryByRole('checkbox', { name: new RegExp(t('goals.workMember.consentCheckbox')) }),
    ).toBeNull()
  })

  it('creates a member without characteristics with no consent required', async () => {
    const user = userEvent.setup()
    const onDone = vi.fn()
    renderWithProviders(<WorkMemberForm goalId={GOAL_ID} onDone={onDone} />)

    await user.type(nameInput(), 'Aさん')
    await user.click(saveButton())

    await waitFor(() =>
      expect(createWorkMember).toHaveBeenCalledWith(GOAL_ID, {
        name: 'Aさん',
        gender: null,
        characteristics: null,
        consent_confirmed: false,
      }),
    )
  })

  it('sends consent_confirmed=true when the checkbox is ticked', async () => {
    const user = userEvent.setup()
    renderWithProviders(<WorkMemberForm goalId={GOAL_ID} onDone={vi.fn()} />)

    await user.type(nameInput(), 'Aさん')
    await user.type(characteristicsInput(), '明るい性格')
    await user.click(consentCheckbox())
    await user.click(saveButton())

    await waitFor(() =>
      expect(createWorkMember).toHaveBeenCalledWith(GOAL_ID, {
        name: 'Aさん',
        gender: null,
        characteristics: '明るい性格',
        consent_confirmed: true,
      }),
    )
  })

  it('sends the selected gender', async () => {
    const user = userEvent.setup()
    renderWithProviders(<WorkMemberForm goalId={GOAL_ID} onDone={vi.fn()} />)

    await user.type(nameInput(), 'Aさん')
    await user.selectOptions(screen.getByLabelText(t('goals.workMember.genderLabel')), 'FEMALE')
    await user.click(saveButton())

    await waitFor(() =>
      expect(createWorkMember).toHaveBeenCalledWith(
        GOAL_ID,
        expect.objectContaining({ gender: 'FEMALE' }),
      ),
    )
  })

  it('resets the consent checkbox when characteristics text changes', async () => {
    const user = userEvent.setup()
    renderWithProviders(<WorkMemberForm goalId={GOAL_ID} onDone={vi.fn()} />)

    await user.type(characteristicsInput(), '明るい性格')
    await user.click(consentCheckbox())
    expect(consentCheckbox()).toHaveProperty('checked', true)

    await user.type(characteristicsInput(), 'さらに追記')

    expect(consentCheckbox()).toHaveProperty('checked', false)
  })

  it('edits an existing member and invalidates on success', async () => {
    const user = userEvent.setup()
    const onDone = vi.fn()
    const member = makeWorkMember({ name: 'Aさん' })
    renderWithProviders(<WorkMemberForm goalId={GOAL_ID} member={member} onDone={onDone} />)

    await user.clear(nameInput())
    await user.type(nameInput(), 'Bさん')
    await user.click(saveButton())

    await waitFor(() =>
      expect(updateWorkMember).toHaveBeenCalledWith(member.id, {
        name: 'Bさん',
        gender: null,
        characteristics: null,
        consent_confirmed: false,
      }),
    )
  })
})
