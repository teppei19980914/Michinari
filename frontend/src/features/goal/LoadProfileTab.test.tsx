/** 負荷プロファイルタブの送信内容と、取り消せない削除のガードを固定する（Phase 35）。
 *
 * 負荷係数は日次ノルマの算出に直接効くため、係数が数値として送られること・備考の空欄が
 * 空文字ではなく `null` として送られることを固定する。文字列のまま送ると係数が無効になり、
 * 空文字を送ると「備考なし」と「空の備考」が区別できなくなる。 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { t } from '../../locales/t'
import { renderWithProviders } from '../../test/renderWithProviders'
import { GOAL_ID, LOAD_PROFILE_ID, makeGoalDetail, makeLoadProfile } from '../../test/fixtures'
import { LoadProfileTab } from './LoadProfileTab'

const createLoadProfile = vi.hoisted(() => vi.fn())
const updateLoadProfile = vi.hoisted(() => vi.fn())
const deleteLoadProfile = vi.hoisted(() => vi.fn())
vi.mock('../../api/goals', () => ({
  createLoadProfile,
  updateLoadProfile,
  deleteLoadProfile,
}))

const DATE_FROM = '2026-10-01'
const DATE_TO = '2026-10-31'

const addButton = () => screen.getByRole('button', { name: t('goals.loadProfile.addTitle') })
const saveButton = () => screen.getByRole('button', { name: t('common.action.save') })
const editButton = () => screen.getByRole('button', { name: t('common.action.edit') })
const deleteButton = () => screen.getByRole('button', { name: t('common.action.delete') })
const cancelButton = () => screen.getByRole('button', { name: t('common.action.cancel') })
const dateInputs = (container: HTMLElement) =>
  Array.from(container.querySelectorAll<HTMLInputElement>('input[type="date"]'))

function setDate(input: HTMLInputElement, value: string) {
  fireEvent.change(input, { target: { value } })
}

const goalWith = (profiles = [makeLoadProfile()]) => makeGoalDetail({ load_profiles: profiles })

beforeEach(() => {
  vi.clearAllMocks()
  createLoadProfile.mockResolvedValue(makeLoadProfile())
  updateLoadProfile.mockResolvedValue(makeLoadProfile())
  deleteLoadProfile.mockResolvedValue(undefined)
})

afterEach(() => {
  cleanup()
})

describe('LoadProfileTab の一覧', () => {
  it('shows the empty message when the goal has no profile', () => {
    renderWithProviders(<LoadProfileTab goal={goalWith([])} readOnly={false} />)

    expect(screen.getByText(t('goals.loadProfile.empty'))).toBeDefined()
  })

  it('hides every editing action when read only', () => {
    renderWithProviders(<LoadProfileTab goal={goalWith()} readOnly />)

    expect(screen.queryByRole('button', { name: t('common.action.edit') })).toBeNull()
    expect(screen.queryByRole('button', { name: t('common.action.delete') })).toBeNull()
    expect(screen.queryByRole('button', { name: t('goals.loadProfile.addTitle') })).toBeNull()
  })

  it('appends the note in parentheses only when there is one', () => {
    const { unmount } = renderWithProviders(<LoadProfileTab goal={goalWith()} readOnly />)
    expect(screen.getByText(/\(繁忙期\)/)).toBeDefined()

    unmount()
    renderWithProviders(
      <LoadProfileTab goal={goalWith([makeLoadProfile({ note: null })])} readOnly />,
    )

    expect(screen.queryByText(/\(/)).toBeNull()
  })
})

describe('LoadProfileTab の取り消せない操作', () => {
  it('does not delete when the confirmation is dismissed', async () => {
    const user = userEvent.setup()
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(false)
    renderWithProviders(<LoadProfileTab goal={goalWith()} readOnly={false} />)

    await user.click(deleteButton())

    expect(confirmSpy).toHaveBeenCalledOnce()
    expect(deleteLoadProfile).not.toHaveBeenCalled()
  })

  it('deletes only after the confirmation is accepted', async () => {
    const user = userEvent.setup()
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    renderWithProviders(<LoadProfileTab goal={goalWith()} readOnly={false} />)

    await user.click(deleteButton())

    await waitFor(() => expect(deleteLoadProfile).toHaveBeenCalledWith(LOAD_PROFILE_ID))
  })
})

describe('LoadProfileTab の送信内容', () => {
  it('creates a profile with a numeric coefficient and a null note', async () => {
    const user = userEvent.setup()
    const { container } = renderWithProviders(
      <LoadProfileTab goal={goalWith([])} readOnly={false} />,
    )

    await user.click(addButton())
    setDate(dateInputs(container)[0], DATE_FROM)
    setDate(dateInputs(container)[1], DATE_TO)
    await user.click(saveButton())

    await waitFor(() => expect(createLoadProfile).toHaveBeenCalledOnce())
    expect(createLoadProfile).toHaveBeenCalledWith(GOAL_ID, {
      date_from: DATE_FROM,
      date_to: DATE_TO,
      // 既定値 '1.0' は文字列のまま送らず数値へ直す。
      coefficient: 1,
      // 備考の空欄は空文字ではなく未設定として送る。
      note: null,
    })
  })

  it('sends the entered coefficient and note', async () => {
    const user = userEvent.setup()
    const { container } = renderWithProviders(
      <LoadProfileTab goal={goalWith([])} readOnly={false} />,
    )

    await user.click(addButton())
    setDate(dateInputs(container)[0], DATE_FROM)
    setDate(dateInputs(container)[1], DATE_TO)
    await user.clear(screen.getByLabelText(t('goals.loadProfile.coefficientLabel')))
    await user.type(screen.getByLabelText(t('goals.loadProfile.coefficientLabel')), '0.5')
    await user.type(screen.getByLabelText(t('goals.loadProfile.noteLabel')), '出張')
    await user.click(saveButton())

    await waitFor(() => expect(createLoadProfile).toHaveBeenCalledOnce())
    expect(createLoadProfile.mock.calls[0][1]).toMatchObject({ coefficient: 0.5, note: '出張' })
  })

  it('updates the existing profile instead of creating a new one', async () => {
    const user = userEvent.setup()
    renderWithProviders(<LoadProfileTab goal={goalWith()} readOnly={false} />)

    await user.click(editButton())
    await user.click(saveButton())

    await waitFor(() => expect(updateLoadProfile).toHaveBeenCalledOnce())
    expect(updateLoadProfile.mock.calls[0][0]).toBe(LOAD_PROFILE_ID)
    expect(createLoadProfile).not.toHaveBeenCalled()
  })

  it('closes the form without sending anything on cancel', async () => {
    const user = userEvent.setup()
    renderWithProviders(<LoadProfileTab goal={goalWith([])} readOnly={false} />)

    await user.click(addButton())
    await user.click(cancelButton())

    expect(createLoadProfile).not.toHaveBeenCalled()
    expect(addButton()).toBeDefined()
  })

  it('leaves the edit form without sending anything on cancel', async () => {
    const user = userEvent.setup()
    renderWithProviders(<LoadProfileTab goal={goalWith()} readOnly={false} />)

    await user.click(editButton())
    await user.click(cancelButton())

    expect(updateLoadProfile).not.toHaveBeenCalled()
    expect(editButton()).toBeDefined()
  })
})
