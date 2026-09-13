/** 月次報告・半期評価タブの、種別による呼び分けと送信内容を固定する（Phase 35）。
 *
 * この画面は `kind`（monthly / semiannual）ひとつで、呼ぶAPI・見出し語・送信する項目を切り替える。
 * 取り違えると半期評価の内容が月次報告として保存されるなど、後から気づきにくい形で壊れる。
 * 特記事項（`report_notes`）は月次にしか存在しないため、半期では送らないことを固定する。 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { t } from '../../locales/t'
import { renderWithProviders } from '../../test/renderWithProviders'
import { GOAL_ID, MONTHLY_PERIOD_KEY, makeWorkReport } from '../../test/fixtures'
import { WorkReportTab } from './WorkReportTab'

const getMonthlyReport = vi.hoisted(() => vi.fn())
const getSemiannualReview = vi.hoisted(() => vi.fn())
const generateMonthlyReport = vi.hoisted(() => vi.fn())
const generateSemiannualReview = vi.hoisted(() => vi.fn())
const updateMonthlyReport = vi.hoisted(() => vi.fn())
const updateSemiannualReview = vi.hoisted(() => vi.fn())
vi.mock('../../api/closure', () => ({
  getMonthlyReport,
  getSemiannualReview,
  generateMonthlyReport,
  generateSemiannualReview,
  updateMonthlyReport,
  updateSemiannualReview,
}))

// ブラウザAPI（URL.createObjectURL）に直接触るため差し替える。
const downloadBlob = vi.hoisted(() => vi.fn())
vi.mock('../../utils/downloadBlob', () => ({ downloadBlob }))

const saveButton = () => screen.getByRole('button', { name: t('common.action.save') })
const downloadButton = () =>
  screen.getByRole('button', { name: t('goals.workReport.downloadButton') })
const generateButton = () =>
  screen.getByRole('button', { name: t('goals.workReport.generateButton') })
const regenerateButton = () =>
  screen.getByRole('button', { name: t('goals.workReport.regenerateButton') })
const scoreSelect = () => screen.getByLabelText(t('goals.workReport.achievementScoreLabel'))

beforeEach(() => {
  vi.clearAllMocks()
  getMonthlyReport.mockResolvedValue(makeWorkReport())
  getSemiannualReview.mockResolvedValue(
    makeWorkReport({ period_type: 'SEMI_ANNUAL', period_key: '2026-H1', report_notes: null }),
  )
  generateMonthlyReport.mockResolvedValue(makeWorkReport())
  generateSemiannualReview.mockResolvedValue(
    makeWorkReport({ period_type: 'SEMI_ANNUAL', period_key: '2026-H1' }),
  )
  updateMonthlyReport.mockResolvedValue(makeWorkReport())
  updateSemiannualReview.mockResolvedValue(
    makeWorkReport({ period_type: 'SEMI_ANNUAL', period_key: '2026-H1' }),
  )
})

afterEach(() => {
  cleanup()
})

describe('WorkReportTab の種別による呼び分け', () => {
  it('reads the monthly report for the monthly kind', async () => {
    renderWithProviders(<WorkReportTab goalId={GOAL_ID} kind="monthly" />)

    await waitFor(() => expect(getMonthlyReport).toHaveBeenCalledWith(GOAL_ID, undefined))
    expect(getSemiannualReview).not.toHaveBeenCalled()
    expect(screen.getByLabelText(t('goals.workReport.periodLabelMonthly'))).toBeDefined()
  })

  it('reads the semiannual review for the semiannual kind', async () => {
    renderWithProviders(<WorkReportTab goalId={GOAL_ID} kind="semiannual" />)

    await waitFor(() => expect(getSemiannualReview).toHaveBeenCalledWith(GOAL_ID, undefined))
    expect(getMonthlyReport).not.toHaveBeenCalled()
    expect(screen.getByLabelText(t('goals.workReport.periodLabelSemiannual'))).toBeDefined()
  })

  it('shows the notes field only for the monthly report', async () => {
    const { unmount } = renderWithProviders(<WorkReportTab goalId={GOAL_ID} kind="monthly" />)
    expect(await screen.findByLabelText(t('goals.workReport.reportNotesLabel'))).toBeDefined()

    unmount()
    renderWithProviders(<WorkReportTab goalId={GOAL_ID} kind="semiannual" />)

    await screen.findByLabelText(t('goals.workReport.businessSummaryLabel'))
    expect(screen.queryByLabelText(t('goals.workReport.reportNotesLabel'))).toBeNull()
  })

  it('labels the next goal field per kind', async () => {
    const { unmount } = renderWithProviders(<WorkReportTab goalId={GOAL_ID} kind="monthly" />)
    expect(
      await screen.findByLabelText(t('goals.workReport.nextGoalTextLabelMonthly')),
    ).toBeDefined()

    unmount()
    renderWithProviders(<WorkReportTab goalId={GOAL_ID} kind="semiannual" />)

    expect(
      await screen.findByLabelText(t('goals.workReport.nextGoalTextLabelSemiannual')),
    ).toBeDefined()
  })
})

describe('WorkReportTab の表示', () => {
  it('tells the user nothing has been generated yet', async () => {
    getMonthlyReport.mockResolvedValue(null)
    renderWithProviders(<WorkReportTab goalId={GOAL_ID} kind="monthly" />)

    expect(await screen.findByText(t('goals.workReport.empty'))).toBeDefined()
    // 未生成のうちは「生成」、生成済みなら「再生成」と出し分ける。
    expect(generateButton()).toBeDefined()
  })

  it('offers regenerating once a report exists', async () => {
    renderWithProviders(<WorkReportTab goalId={GOAL_ID} kind="monthly" />)

    await waitFor(() => expect(regenerateButton()).toBeDefined())
  })

  it('fills the form from the stored report', async () => {
    renderWithProviders(<WorkReportTab goalId={GOAL_ID} kind="monthly" />)

    expect(
      (
        (await screen.findByLabelText(
          t('goals.workReport.businessSummaryLabel'),
        )) as HTMLTextAreaElement
      ).value,
    ).toBe('業務内容の要約')
    expect((scoreSelect() as HTMLSelectElement).value).toBe('3')
  })

  it('leaves the fields empty when the stored report has no text yet', async () => {
    getMonthlyReport.mockResolvedValue(
      makeWorkReport({
        business_summary: null,
        target_goal_text: null,
        achievement_score: null,
        achievement_reflection: null,
        next_goal_text: null,
        report_notes: null,
      }),
    )
    renderWithProviders(<WorkReportTab goalId={GOAL_ID} kind="monthly" />)

    const summary = (await screen.findByLabelText(
      t('goals.workReport.businessSummaryLabel'),
    )) as HTMLTextAreaElement
    expect(summary.value).toBe('')
    expect((scoreSelect() as HTMLSelectElement).value).toBe('')
  })
})

describe('WorkReportTab の生成と保存', () => {
  it('generates for the period the user typed', async () => {
    const user = userEvent.setup()
    renderWithProviders(<WorkReportTab goalId={GOAL_ID} kind="monthly" />)

    await waitFor(() => expect(regenerateButton()).toBeDefined())
    await user.type(screen.getByLabelText(t('goals.workReport.periodLabelMonthly')), '2026-08')
    await user.click(regenerateButton())

    await waitFor(() => expect(generateMonthlyReport).toHaveBeenCalledWith(GOAL_ID, '2026-08'))
  })

  it('omits the period when the field is left empty so the server picks the current one', async () => {
    const user = userEvent.setup()
    renderWithProviders(<WorkReportTab goalId={GOAL_ID} kind="monthly" />)

    await waitFor(() => expect(regenerateButton()).toBeDefined())
    await user.click(regenerateButton())

    // 空欄を空文字のまま送るとサーバ側で期間として解釈できないため、キーごと省く。
    await waitFor(() => expect(generateMonthlyReport).toHaveBeenCalledWith(GOAL_ID, undefined))
  })

  it('saves the edited monthly report including the notes', async () => {
    const user = userEvent.setup()
    renderWithProviders(<WorkReportTab goalId={GOAL_ID} kind="monthly" />)

    const reflection = (await screen.findByLabelText(
      t('goals.workReport.achievementReflectionLabel'),
    )) as HTMLTextAreaElement
    await user.clear(reflection)
    await user.type(reflection, '書き直した振り返り')
    await user.selectOptions(scoreSelect(), '5')
    await user.click(saveButton())

    await waitFor(() => expect(updateMonthlyReport).toHaveBeenCalledOnce())
    expect(updateMonthlyReport).toHaveBeenCalledWith(GOAL_ID, MONTHLY_PERIOD_KEY, {
      target_goal_text: '当月の目標',
      business_summary: '業務内容の要約',
      achievement_score: 5,
      achievement_reflection: '書き直した振り返り',
      next_goal_text: '翌月の目標',
      report_notes: '特記事項',
    })
    expect(await screen.findByText(t('common.saveSucceeded'))).toBeDefined()
  })

  it('saves every field the reviewer rewrote', async () => {
    const user = userEvent.setup()
    renderWithProviders(<WorkReportTab goalId={GOAL_ID} kind="monthly" />)

    // 生成された下書きは、そのまま提出せず人が書き直す前提の画面である（ロジック・プロンプト編17.9）。
    // どの欄の書き換えも送信へ届くことを確かめる。
    const rewrite = async (labelKey: string, text: string) => {
      const field = screen.getByLabelText(labelKey) as HTMLTextAreaElement
      await user.clear(field)
      await user.type(field, text)
    }

    await screen.findByLabelText(t('goals.workReport.businessSummaryLabel'))
    await rewrite(t('goals.workReport.targetGoalTextLabel'), '書き直した目標')
    await rewrite(t('goals.workReport.businessSummaryLabel'), '書き直した要約')
    await rewrite(t('goals.workReport.nextGoalTextLabelMonthly'), '書き直した翌月目標')
    await rewrite(t('goals.workReport.reportNotesLabel'), '書き直した特記事項')
    await user.click(saveButton())

    await waitFor(() => expect(updateMonthlyReport).toHaveBeenCalledOnce())
    expect(updateMonthlyReport.mock.calls[0][2]).toMatchObject({
      target_goal_text: '書き直した目標',
      business_summary: '書き直した要約',
      next_goal_text: '書き直した翌月目標',
      report_notes: '書き直した特記事項',
    })
  })

  it('omits the notes when saving a semiannual review', async () => {
    const user = userEvent.setup()
    renderWithProviders(<WorkReportTab goalId={GOAL_ID} kind="semiannual" />)

    await screen.findByLabelText(t('goals.workReport.businessSummaryLabel'))
    await user.click(saveButton())

    await waitFor(() => expect(updateSemiannualReview).toHaveBeenCalledOnce())
    // 半期評価に特記事項の項目はないため、キーごと送らない。
    expect(updateSemiannualReview.mock.calls[0][2]).not.toHaveProperty('report_notes')
    expect(updateMonthlyReport).not.toHaveBeenCalled()
  })

  it('sends null when the achievement score is cleared', async () => {
    const user = userEvent.setup()
    renderWithProviders(<WorkReportTab goalId={GOAL_ID} kind="monthly" />)

    await screen.findByLabelText(t('goals.workReport.businessSummaryLabel'))
    await user.selectOptions(scoreSelect(), '')
    await user.click(saveButton())

    await waitFor(() => expect(updateMonthlyReport).toHaveBeenCalledOnce())
    expect(updateMonthlyReport.mock.calls[0][2]).toMatchObject({ achievement_score: null })
  })

  it('downloads the generated body as markdown named after the period', async () => {
    const user = userEvent.setup()
    renderWithProviders(<WorkReportTab goalId={GOAL_ID} kind="monthly" />)

    await waitFor(() => expect(downloadButton()).toBeDefined())
    await user.click(downloadButton())

    expect(downloadBlob).toHaveBeenCalledOnce()
    expect(downloadBlob.mock.calls[0][1]).toBe(`monthly-${MONTHLY_PERIOD_KEY}.md`)
  })
})
