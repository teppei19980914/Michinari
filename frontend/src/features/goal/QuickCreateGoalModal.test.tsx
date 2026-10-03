/** 読書・仕事の簡易作成の送信内容を固定する。
 *
 * 総ページ数・想定業務内容はバックエンドでは必須だが、この簡易フォームでは任意入力の
 * ため、未入力時に暫定値（総ページ数1、想定業務内容は案件名）を補って送っていることを
 * 検証する（quickCreateGoalDefaults.test.ts が担う純粋関数の呼び出し結果の確認）。 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { t } from '../../locales/t'
import { renderWithProviders } from '../../test/renderWithProviders'
import { makeGoal } from '../../test/fixtures'
import { QuickCreateGoalModal } from './QuickCreateGoalModal'

const createGoal = vi.hoisted(() => vi.fn())
const createBook = vi.hoisted(() => vi.fn())
const createWorkAssignment = vi.hoisted(() => vi.fn())
const activateGoal = vi.hoisted(() => vi.fn())
vi.mock('../../api/goals', () => ({ createGoal, createBook, createWorkAssignment, activateGoal }))

const getToday = vi.hoisted(() => vi.fn())
vi.mock('../../api/records', () => ({ getToday }))

const TODAY = '2026-05-01'
const CREATED_GOAL = makeGoal({ id: 42 })

const cancelButton = () => screen.getByRole('button', { name: t('common.action.cancel') })
const submitButton = () => screen.getByRole('button', { name: t('goals.new.quickCreate.submitButton') })

beforeEach(() => {
  vi.clearAllMocks()
  getToday.mockResolvedValue({ logical_date: TODAY })
  createGoal.mockResolvedValue(CREATED_GOAL)
  createBook.mockResolvedValue({})
  createWorkAssignment.mockResolvedValue({})
  activateGoal.mockResolvedValue(CREATED_GOAL)
})

afterEach(() => {
  cleanup()
})

describe('QuickCreateGoalModal（読書）', () => {
  it('sends the entered author and total pages, then activates the goal', async () => {
    const user = userEvent.setup()
    const onCreated = vi.fn()
    renderWithProviders(
      <QuickCreateGoalModal open category="READING" onClose={() => {}} onCreated={onCreated} />,
    )
    await waitFor(() => expect(getToday).toHaveBeenCalled())

    await user.type(screen.getByLabelText(t('goals.new.quickCreate.reading.titleLabel')), '銀河鉄道の夜')
    await user.type(screen.getByLabelText(t('goals.new.quickCreate.reading.authorLabel')), '宮沢賢治')
    await user.type(screen.getByLabelText(t('goals.new.quickCreate.reading.totalPagesLabel')), '200')
    await user.click(submitButton())

    await waitFor(() => expect(activateGoal).toHaveBeenCalledWith(CREATED_GOAL.id))
    expect(createGoal).toHaveBeenCalledWith({
      category: 'READING',
      name: '銀河鉄道の夜',
      start_date: TODAY,
    })
    expect(createBook).toHaveBeenCalledWith(CREATED_GOAL.id, {
      title: '銀河鉄道の夜',
      author: '宮沢賢治',
      total_pages: 200,
      start_date: TODAY,
      due_date: '2026-07-30',
    })
    expect(onCreated).toHaveBeenCalledWith(CREATED_GOAL.id)
  })

  it('fills in placeholder defaults when author and total pages are left blank', async () => {
    const user = userEvent.setup()
    renderWithProviders(
      <QuickCreateGoalModal open category="READING" onClose={() => {}} onCreated={() => {}} />,
    )
    await waitFor(() => expect(getToday).toHaveBeenCalled())

    await user.type(screen.getByLabelText(t('goals.new.quickCreate.reading.titleLabel')), '銀河鉄道の夜')
    await user.click(submitButton())

    await waitFor(() => expect(createBook).toHaveBeenCalledOnce())
    expect(createBook.mock.calls[0][1]).toMatchObject({ author: null, total_pages: 1 })
  })
})

describe('QuickCreateGoalModal（仕事）', () => {
  it('sends the entered summary as the expected content', async () => {
    const user = userEvent.setup()
    const onCreated = vi.fn()
    renderWithProviders(
      <QuickCreateGoalModal open category="WORK" onClose={() => {}} onCreated={onCreated} />,
    )
    await waitFor(() => expect(getToday).toHaveBeenCalled())

    await user.type(screen.getByLabelText(t('goals.new.quickCreate.work.nameLabel')), '新規案件A')
    await user.type(screen.getByLabelText(t('goals.new.quickCreate.work.summaryLabel')), '保守運用')
    await user.click(submitButton())

    await waitFor(() => expect(activateGoal).toHaveBeenCalledWith(CREATED_GOAL.id))
    expect(createWorkAssignment).toHaveBeenCalledWith(CREATED_GOAL.id, {
      client_name: null,
      expected_content: '保守運用',
      start_date: TODAY,
    })
    expect(onCreated).toHaveBeenCalledWith(CREATED_GOAL.id)
  })

  it('falls back to the goal name as the expected content when the summary is blank', async () => {
    const user = userEvent.setup()
    renderWithProviders(
      <QuickCreateGoalModal open category="WORK" onClose={() => {}} onCreated={() => {}} />,
    )
    await waitFor(() => expect(getToday).toHaveBeenCalled())

    await user.type(screen.getByLabelText(t('goals.new.quickCreate.work.nameLabel')), '新規案件A')
    await user.click(submitButton())

    await waitFor(() => expect(createWorkAssignment).toHaveBeenCalledOnce())
    expect(createWorkAssignment.mock.calls[0][1]).toMatchObject({ expected_content: '新規案件A' })
  })
})

describe('QuickCreateGoalModal のキャンセル', () => {
  it('closes without sending anything', async () => {
    const user = userEvent.setup()
    const onClose = vi.fn()
    renderWithProviders(
      <QuickCreateGoalModal open category="READING" onClose={onClose} onCreated={() => {}} />,
    )

    await user.click(cancelButton())

    expect(onClose).toHaveBeenCalledOnce()
    expect(createGoal).not.toHaveBeenCalled()
  })
})
