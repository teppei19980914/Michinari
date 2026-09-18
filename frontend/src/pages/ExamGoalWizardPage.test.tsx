/** 資格ウィザードの一連の流れ（テンプレート選択→受験日→教材→時間設定→開始）と、
 * 既存スロットがある場合の分岐を固定する。 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { t } from '../locales/t'
import { ROUTES } from '../constants/routes'
import { renderWithProviders } from '../test/renderWithProviders'
import { ExamGoalWizardPage } from './ExamGoalWizardPage'

const listExamTemplates = vi.hoisted(() => vi.fn())
vi.mock('../api/examTemplates', () => ({ listExamTemplates }))

const createGoal = vi.hoisted(() => vi.fn())
const createSubject = vi.hoisted(() => vi.fn())
const deleteSubject = vi.hoisted(() => vi.fn())
const createMaterial = vi.hoisted(() => vi.fn())
const deleteMaterial = vi.hoisted(() => vi.fn())
const activateGoal = vi.hoisted(() => vi.fn())
const listSlotAllocations = vi.hoisted(() => vi.fn())
const updateSlotAllocations = vi.hoisted(() => vi.fn())
vi.mock('../api/goals', () => ({
  createGoal,
  createSubject,
  deleteSubject,
  createMaterial,
  deleteMaterial,
  activateGoal,
  listSlotAllocations,
  updateSlotAllocations,
}))

const listSlots = vi.hoisted(() => vi.fn())
const createSlot = vi.hoisted(() => vi.fn())
vi.mock('../api/resources', () => ({ listSlots, createSlot }))

const getToday = vi.hoisted(() => vi.fn())
vi.mock('../api/records', () => ({ getToday }))

const navigate = vi.hoisted(() => vi.fn())
vi.mock('react-router-dom', async (importOriginal) => ({
  ...(await importOriginal<typeof import('react-router-dom')>()),
  useNavigate: () => navigate,
}))

const TEMPLATE = {
  id: 'fe',
  exam_name: '基本情報技術者試験',
  subjects: [
    { name: '科目A', passing_score_type: 'PERCENTAGE' as const, passing_score: 60 },
    { name: '科目B', passing_score_type: 'PERCENTAGE' as const, passing_score: 60 },
  ],
  materials: [
    { name: '教科書', unit_label: 'ページ', total_amount: 500, planned_cycles: 1, subject_names: ['科目A', '科目B'] },
  ],
}

const nextButton = () => screen.getByRole('button', { name: t('common.action.next') }) as HTMLButtonElement
const backButton = () => screen.getByRole('button', { name: t('common.action.back') }) as HTMLButtonElement

/** Step2の受験日欄（科目ごとに開始・終了の2つ、出現順）へ日付を入れる。 */
function fillExamDates() {
  const dateInputs = document.querySelectorAll<HTMLInputElement>('input[type="date"]')
  dateInputs.forEach((input, index) => {
    fireEvent.change(input, { target: { value: index % 2 === 0 ? '2026-11-01' : '2026-11-30' } })
  })
  return dateInputs
}

beforeEach(() => {
  vi.clearAllMocks()
  listExamTemplates.mockResolvedValue([TEMPLATE])
  getToday.mockResolvedValue({ logical_date: '2026-09-20' })
  listSlots.mockResolvedValue([])
  createGoal.mockResolvedValue({ id: 1 })
  createSubject.mockResolvedValueOnce({ id: 11, name: '科目A' }).mockResolvedValueOnce({ id: 12, name: '科目B' })
  createMaterial.mockResolvedValue({ id: 21 })
  createSlot.mockResolvedValue({ id: 31 })
  updateSlotAllocations.mockResolvedValue(undefined)
  activateGoal.mockResolvedValue({ id: 1 })
})

afterEach(() => {
  cleanup()
})

describe('ExamGoalWizardPage の一連の流れ（テンプレート・スロット未設定）', () => {
  it('creates the goal, subjects, materials, a weekday slot and activates the goal', async () => {
    const user = userEvent.setup()
    renderWithProviders(<ExamGoalWizardPage />)

    // Step1: テンプレートを選ぶ。
    await user.click(await screen.findByText(TEMPLATE.exam_name))
    await user.click(nextButton())
    await waitFor(() => expect(createGoal).toHaveBeenCalledWith({
      category: 'EXAM',
      name: TEMPLATE.exam_name,
      start_date: '2026-09-20',
    }))

    // Step2: 科目ごとに受験日を入れる（期間指定、既定のまま）。
    await screen.findByText(t('goals.examWizard.step2.description'))
    expect(fillExamDates().length).toBe(4)
    await user.click(nextButton())
    await waitFor(() => expect(createSubject).toHaveBeenCalledTimes(2), { timeout: 8000 })

    // Step3: 教材はテンプレートの内容のまま次へ。
    await screen.findByText(t('goals.examWizard.step3.description'))
    await user.click(nextButton())
    await waitFor(() => expect(createMaterial).toHaveBeenCalledOnce(), { timeout: 8000 })
    expect(createMaterial).toHaveBeenCalledWith(1, {
      name: '教科書',
      unit_label: 'ページ',
      total_amount: 500,
      planned_cycles: 1,
      subject_ids: [11, 12],
      start_date: '2026-09-20',
      due_date_is_manual: false,
      required_environment: 'ANY',
      quality_metric_type: 'NONE',
    })

    // Step4: スロット未設定のため簡易時間設定。平日2時間のみ入力。
    await screen.findByLabelText(t('goals.examWizard.step4.weekdayHoursLabel'))
    await user.type(screen.getByLabelText(t('goals.examWizard.step4.weekdayHoursLabel')), '2')
    await user.click(nextButton())
    await waitFor(() => expect(createSlot).toHaveBeenCalledOnce(), { timeout: 8000 })
    expect(updateSlotAllocations).toHaveBeenCalledWith(1, {
      allocations: [{ slot_id: 31, minutes: 120 }],
    })

    // Step5: 確認して開始する。
    await screen.findByText(t('goals.examWizard.step5.advancedSettingsNotice'))
    await user.click(screen.getByRole('button', { name: t('goals.examWizard.startButton') }))

    await waitFor(() => expect(activateGoal).toHaveBeenCalledWith(1), { timeout: 8000 })
    expect(navigate).toHaveBeenCalledWith(ROUTES.dashboard, {
      state: { showFirstRecordBanner: true },
    })
  }, 15000)

  it('disables next until a template (or manual name) is chosen', async () => {
    renderWithProviders(<ExamGoalWizardPage />)

    await screen.findByText(TEMPLATE.exam_name)
    expect(nextButton().disabled).toBe(true)
  })

  it('disables back on the first step', async () => {
    renderWithProviders(<ExamGoalWizardPage />)

    await screen.findByText(TEMPLATE.exam_name)
    expect(backButton().disabled).toBe(true)
  })

  it('lets the user enter an exam name manually via the other option', async () => {
    const user = userEvent.setup()
    renderWithProviders(<ExamGoalWizardPage />)

    await user.click(await screen.findByText(t('goals.examWizard.step1.otherOption')))
    await user.type(screen.getByLabelText(t('goals.examWizard.step1.examNameLabel')), '自分だけの試験')

    expect(nextButton().disabled).toBe(false)
  })
})

describe('ExamGoalWizardPage の既存スロット分岐', () => {
  it('shows the allocation table instead of the simple hour inputs when slots already exist', async () => {
    const user = userEvent.setup()
    listSlots.mockResolvedValue([{ id: 41, name: '通勤時間' }])
    listSlotAllocations.mockResolvedValue([
      {
        slot_id: 41,
        slot_name: '通勤時間',
        environment: 'MOBILE',
        weekdays: [0, 1, 2, 3, 4],
        duration_minutes: 60,
        others_minutes: 0,
        minutes: 0,
        is_over_capacity: false,
      },
    ])
    renderWithProviders(<ExamGoalWizardPage />)

    await user.click(await screen.findByText(TEMPLATE.exam_name))
    await user.click(nextButton())
    await waitFor(() => expect(createGoal).toHaveBeenCalledOnce())

    await waitFor(() =>
      expect(document.querySelectorAll('input[type="date"]').length).toBe(4),
    )
    fillExamDates()
    await user.click(nextButton())
    await waitFor(() => expect(createSubject).toHaveBeenCalledTimes(2), { timeout: 8000 })

    await screen.findByText(t('goals.examWizard.step3.description'))
    await user.click(nextButton())
    await waitFor(() => expect(createMaterial).toHaveBeenCalledOnce(), { timeout: 8000 })
    await user.click(nextButton())

    await screen.findByText(t('goals.examWizard.step4.existingSlotsDescription'))
    expect(screen.queryByLabelText(t('goals.examWizard.step4.weekdayHoursLabel'))).toBeNull()

    const minutesInput = within(screen.getByText('通勤時間').closest('tr') as HTMLElement).getByRole(
      'spinbutton',
    )
    await user.type(minutesInput, '30')
    await user.click(nextButton())

    await waitFor(
      () =>
        expect(updateSlotAllocations).toHaveBeenCalledWith(1, {
          allocations: [{ slot_id: 41, minutes: 30 }],
        }),
      { timeout: 8000 },
    )
    expect(createSlot).not.toHaveBeenCalled()
  }, 15000)
})
