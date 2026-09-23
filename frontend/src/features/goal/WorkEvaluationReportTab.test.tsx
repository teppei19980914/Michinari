/** AI評価レポートタブのロール分岐・生成→レビュー→保存の流れを固定する（要件定義書6.11）。 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { t } from '../../locales/t'
import { renderWithProviders } from '../../test/renderWithProviders'
import { GOAL_ID, makeGoalDetail, makeWorkAssignment, makeWorkMember } from '../../test/fixtures'
import { WorkEvaluationReportTab } from './WorkEvaluationReportTab'

const generateEvaluationReport = vi.hoisted(() => vi.fn())
const listEvaluationReports = vi.hoisted(() => vi.fn())
const updateEvaluationReport = vi.hoisted(() => vi.fn())
vi.mock('../../api/closure', () => ({
  generateEvaluationReport,
  listEvaluationReports,
  updateEvaluationReport,
}))

const getAiStatus = vi.hoisted(() => vi.fn())
vi.mock('../../api/ai', () => ({ getAiStatus }))

const REPORT = {
  id: 1,
  work_assignment_id: 10,
  member_id: 1,
  member_name: 'Aさん',
  considerations: '納期意識を評価してほしい',
  body: '生成されたレポート本文',
  generated_at: '2026-02-01T00:00:00Z',
  edited_at: null,
}

beforeEach(() => {
  vi.clearAllMocks()
  getAiStatus.mockResolvedValue({ authenticated: true })
  listEvaluationReports.mockResolvedValue([])
  generateEvaluationReport.mockResolvedValue(REPORT)
  updateEvaluationReport.mockResolvedValue({ ...REPORT, body: '修正後の本文', edited_at: '2026-02-02T00:00:00Z' })
})

afterEach(() => {
  cleanup()
})

const goalWithRole = (role: 'EVALUATOR' | 'EVALUATEE' | null, members = [makeWorkMember()]) =>
  makeGoalDetail({
    category: 'WORK',
    work_assignment: makeWorkAssignment({ role, members }),
  })

describe('WorkEvaluationReportTab', () => {
  it('shows a notice instead of the form when role is not EVALUATOR', () => {
    renderWithProviders(<WorkEvaluationReportTab goal={goalWithRole('EVALUATEE')} />)

    expect(screen.getByText(t('goals.workEvaluationReport.roleRequiredNotice'))).toBeDefined()
    expect(screen.queryByRole('button', { name: t('goals.workEvaluationReport.generateButton') })).toBeNull()
  })

  it('shows a notice when there are no active members', () => {
    renderWithProviders(<WorkEvaluationReportTab goal={goalWithRole('EVALUATOR', [])} />)

    expect(screen.getByText(t('goals.workEvaluationReport.memberRequiredNotice'))).toBeDefined()
  })

  it('excludes inactive members from the picker', () => {
    const inactive = makeWorkMember({ id: 2, name: 'Bさん', is_active: false })
    renderWithProviders(
      <WorkEvaluationReportTab goal={goalWithRole('EVALUATOR', [makeWorkMember(), inactive])} />,
    )

    expect(screen.queryByRole('option', { name: 'Bさん' })).toBeNull()
  })

  it('disables the generate button until a member and considerations are entered', async () => {
    const user = userEvent.setup()
    const member = makeWorkMember()
    renderWithProviders(<WorkEvaluationReportTab goal={goalWithRole('EVALUATOR', [member])} />)

    const button = screen.getByRole('button', { name: t('goals.workEvaluationReport.generateButton') })
    expect(button).toHaveProperty('disabled', true)

    const memberSelect = screen.getByLabelText(t('goals.workEvaluationReport.memberSelectLabel'))
    await user.selectOptions(memberSelect, String(member.id))
    await user.type(
      screen.getByLabelText(t('goals.workEvaluationReport.considerationsLabel')),
      '考慮事項',
    )

    expect(button).toHaveProperty('disabled', false)

    // 選択解除（空欄に戻す）でも再び無効化される。
    await user.selectOptions(memberSelect, '')
    expect(button).toHaveProperty('disabled', true)
  })

  it('shows the AI-unconfigured notice instead of the generate button', async () => {
    getAiStatus.mockResolvedValue({ authenticated: false })
    renderWithProviders(<WorkEvaluationReportTab goal={goalWithRole('EVALUATOR')} />)

    expect(await screen.findByText(t('aiUnconfigured.message'))).toBeDefined()
    expect(
      screen.queryByRole('button', { name: t('goals.workEvaluationReport.generateButton') }),
    ).toBeNull()
  })

  it('generates a report and shows it in the review card', async () => {
    const user = userEvent.setup()
    const member = makeWorkMember()
    renderWithProviders(<WorkEvaluationReportTab goal={goalWithRole('EVALUATOR', [member])} />)

    await user.selectOptions(
      screen.getByLabelText(t('goals.workEvaluationReport.memberSelectLabel')),
      String(member.id),
    )
    await user.type(
      screen.getByLabelText(t('goals.workEvaluationReport.considerationsLabel')),
      '納期意識を評価してほしい',
    )
    await user.click(screen.getByRole('button', { name: t('goals.workEvaluationReport.generateButton') }))

    await waitFor(() =>
      expect(generateEvaluationReport).toHaveBeenCalledWith(GOAL_ID, {
        member_id: member.id,
        considerations: '納期意識を評価してほしい',
      }),
    )
    expect(await screen.findByDisplayValue('生成されたレポート本文')).toBeDefined()

    await user.click(screen.getByRole('button', { name: t('goals.workEvaluationReport.downloadButton') }))
  })

  it('saves edits to the review body', async () => {
    const user = userEvent.setup()
    const member = makeWorkMember()
    renderWithProviders(<WorkEvaluationReportTab goal={goalWithRole('EVALUATOR', [member])} />)

    await user.selectOptions(
      screen.getByLabelText(t('goals.workEvaluationReport.memberSelectLabel')),
      String(member.id),
    )
    await user.type(
      screen.getByLabelText(t('goals.workEvaluationReport.considerationsLabel')),
      '考慮事項',
    )
    await user.click(screen.getByRole('button', { name: t('goals.workEvaluationReport.generateButton') }))
    await screen.findByDisplayValue('生成されたレポート本文')

    const bodyField = screen.getByLabelText(t('goals.workEvaluationReport.bodyLabel'))
    await user.clear(bodyField)
    await user.type(bodyField, '修正後の本文')
    await user.click(screen.getByRole('button', { name: t('goals.workEvaluationReport.saveButton') }))

    await waitFor(() =>
      expect(updateEvaluationReport).toHaveBeenCalledWith(GOAL_ID, REPORT.id, {
        body: '修正後の本文',
      }),
    )
  })

  it('loads a history entry into the review card on click', async () => {
    const user = userEvent.setup()
    listEvaluationReports.mockResolvedValue([REPORT])
    renderWithProviders(<WorkEvaluationReportTab goal={goalWithRole('EVALUATOR')} />)

    const historyButton = await screen.findByRole('button', { name: /Aさん/ })
    await user.click(historyButton)

    expect(await screen.findByDisplayValue('生成されたレポート本文')).toBeDefined()
  })

  it('shows the edited badge for a history entry that has been edited', async () => {
    listEvaluationReports.mockResolvedValue([{ ...REPORT, edited_at: '2026-02-02T00:00:00Z' }])
    renderWithProviders(<WorkEvaluationReportTab goal={goalWithRole('EVALUATOR')} />)

    expect(await screen.findByText(t('goals.workEvaluationReport.editedBadge'))).toBeDefined()
  })
})
