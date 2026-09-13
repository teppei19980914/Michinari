/** SC-13 ナレッジエクスポート（KnowledgeExportPage）の、目標種別ごとの出し分けと送信内容を
 * 固定する回帰テスト（Phase 36）。
 *
 * 1関数100行の上限（CODING_RULES.md「保守性（複雑度）」）への対応で出力項目の選択欄を
 * 切り出すにあたり、先に現状の振る舞いを固定しておくための安全網である。
 *
 * この画面は種別（資格試験・読書・仕事）で選択肢そのものと呼び名が変わる（仕様書6.10、
 * 設計書データ構造編7.1）。読書・仕事に存在しない項目（教材構成・品質指標推移など）を
 * 出すと、該当データが無い項目を選ばせてしまう。総括レポートも仕事目標だけは専用
 * エンドポイントを使えず案内文のみにする必要がある（データ構造編6.2）。
 *
 * カバレッジの扱いは他の画面テストと同じ（vite.config.ts の coverage.exclude で
 * `src/pages/**\/*.tsx` を除外し、振る舞いはこのテストが守る）。 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { t } from '../locales/t'
import { renderWithProviders } from '../test/renderWithProviders'
import { GOAL_ID, makeGoalDetail } from '../test/fixtures'
import type { GoalDetailRead } from '../api/goals'
import { KnowledgeExportPage } from './KnowledgeExportPage'

const getGoal = vi.hoisted(() => vi.fn())
vi.mock('../api/goals', () => ({ getGoal }))

const getRetrospective = vi.hoisted(() => vi.fn())
const generateRetrospective = vi.hoisted(() => vi.fn())
vi.mock('../api/closure', () => ({ getRetrospective, generateRetrospective }))

const previewKnowledgeExport = vi.hoisted(() => vi.fn())
const executeKnowledgeExport = vi.hoisted(() => vi.fn())
const getKnowledgeExportProgress = vi.hoisted(() => vi.fn())
vi.mock('../api/export', () => ({
  previewKnowledgeExport,
  executeKnowledgeExport,
  getKnowledgeExportProgress,
}))

vi.mock('react-router-dom', async (importOriginal) => ({
  ...(await importOriginal<typeof import('react-router-dom')>()),
  useParams: () => ({ goalId: String(GOAL_ID) }),
}))

const GOAL_NAME = '目標A'
const RETROSPECTIVE_BODY = '総括レポートの本文'
/** プレビュー本文。見出しの文言と紛れないよう、画面の文言に現れない文字列にする。 */
const PREVIEW_MARKDOWN = '## markdown-preview-body'

/** 読書・仕事には存在しない出力項目（仕様書6.10）。 */
const EXAM_ONLY_LABEL_KEYS = [
  'knowledgeExport.selection.materials',
  'knowledgeExport.selection.qualityTrend',
  'knowledgeExport.selection.replanHistory',
  'knowledgeExport.selection.weeklySummaries',
  'knowledgeExport.selection.diary',
  'knowledgeExport.selection.aiDialogue',
  'knowledgeExport.selection.examResults',
]

// --- 要素アクセサ ---
const previewButton = () => screen.getByRole('button', { name: t('knowledgeExport.previewButton') })
const exportButton = () => screen.getByRole('button', { name: t('knowledgeExport.exportButton') })
const anonymizeCheckbox = () =>
  screen.getByRole('checkbox', { name: t('knowledgeExport.anonymize.label') })
const selectionCheckbox = (labelKey: string) =>
  screen.getByRole('checkbox', { name: t(labelKey) })

async function renderPage(goal: Partial<GoalDetailRead> = {}) {
  getGoal.mockResolvedValue(makeGoalDetail({ name: GOAL_NAME, ...goal }))
  const result = renderWithProviders(<KnowledgeExportPage />)
  await screen.findByText(t('knowledgeExport.title', { name: GOAL_NAME }))
  return result
}

beforeEach(() => {
  vi.clearAllMocks()
  getRetrospective.mockResolvedValue({ body: RETROSPECTIVE_BODY })
  generateRetrospective.mockResolvedValue({ body: RETROSPECTIVE_BODY })
  previewKnowledgeExport.mockResolvedValue({ data: {}, markdown: PREVIEW_MARKDOWN })
  executeKnowledgeExport.mockResolvedValue({
    data: {},
    markdown: '# 本文',
    markdown_path: '/out/a.md',
    json_path: '/out/a.json',
  })
  getKnowledgeExportProgress.mockResolvedValue({ in_progress: false, completed: 0, total: 0 })
})

afterEach(() => {
  cleanup()
})

describe('KnowledgeExportPage の読み込み', () => {
  it('shows the loading text until the goal arrives', () => {
    getGoal.mockReturnValue(new Promise(() => undefined))
    renderWithProviders(<KnowledgeExportPage />)
    expect(screen.getByText(t('common.loading'))).toBeTruthy()
  })

  it('shows an error when the goal cannot be read', async () => {
    getGoal.mockRejectedValue(new Error('boom'))
    renderWithProviders(<KnowledgeExportPage />)
    expect(await screen.findByText(t('errors.default'))).toBeTruthy()
  })
})

describe('KnowledgeExportPage の出力項目', () => {
  it('offers every item for an exam goal', async () => {
    await renderPage()
    for (const labelKey of EXAM_ONLY_LABEL_KEYS) {
      expect(selectionCheckbox(labelKey)).toBeTruthy()
    }
  })

  it('hides the items that reading goals have no data for', async () => {
    await renderPage({ category: 'READING' })
    for (const labelKey of EXAM_ONLY_LABEL_KEYS) {
      expect(screen.queryByRole('checkbox', { name: t(labelKey) })).toBe(null)
    }
  })

  it('hides the items that work goals have no data for', async () => {
    await renderPage({ category: 'WORK' })
    for (const labelKey of EXAM_ONLY_LABEL_KEYS) {
      expect(screen.queryByRole('checkbox', { name: t(labelKey) })).toBe(null)
    }
  })

  it('renames the shared items for a reading goal', async () => {
    await renderPage({ category: 'READING' })
    expect(selectionCheckbox('knowledgeExport.selection.readingSummary')).toBeTruthy()
    expect(selectionCheckbox('knowledgeExport.selection.readingDailyRecords')).toBeTruthy()
    expect(selectionCheckbox('knowledgeExport.selection.readingRetrospective')).toBeTruthy()
  })

  it('renames the shared items for a work goal', async () => {
    await renderPage({ category: 'WORK' })
    expect(selectionCheckbox('knowledgeExport.selection.workSummary')).toBeTruthy()
    expect(selectionCheckbox('knowledgeExport.selection.workDailyRecords')).toBeTruthy()
    expect(selectionCheckbox('knowledgeExport.selection.workRetrospective')).toBeTruthy()
  })

  it('starts with the diary and the AI dialogue unselected', async () => {
    // 本文をそのまま含める項目は既定でオフにする。
    await renderPage()
    expect((selectionCheckbox('knowledgeExport.selection.diary') as HTMLInputElement).checked)
      .toBe(false)
    expect((selectionCheckbox('knowledgeExport.selection.aiDialogue') as HTMLInputElement).checked)
      .toBe(false)
    expect((selectionCheckbox('knowledgeExport.selection.goalOverview') as HTMLInputElement).checked)
      .toBe(true)
  })

  it('describes the anonymisation per goal category', async () => {
    await renderPage()
    expect(screen.getByText(t('knowledgeExport.anonymize.description'))).toBeTruthy()
    cleanup()
    await renderPage({ category: 'READING' })
    expect(screen.getByText(t('knowledgeExport.anonymize.readingDescription'))).toBeTruthy()
    cleanup()
    await renderPage({ category: 'WORK' })
    expect(screen.getByText(t('knowledgeExport.anonymize.workDescription'))).toBeTruthy()
  })
})

describe('KnowledgeExportPage のプレビューと実行', () => {
  it('previews with the current selection and anonymisation flag', async () => {
    const user = userEvent.setup()
    await renderPage()
    await user.click(selectionCheckbox('knowledgeExport.selection.diary'))
    await user.click(anonymizeCheckbox())
    await user.click(previewButton())

    await waitFor(() => expect(previewKnowledgeExport).toHaveBeenCalledOnce())
    const [goalId, selection, anonymize] = previewKnowledgeExport.mock.calls[0]
    expect(goalId).toBe(GOAL_ID)
    expect(selection.diary).toBe(true)
    expect(selection.goal_overview).toBe(true)
    expect(anonymize).toBe(true)
    // 選択は selection、匿名化は別引数で渡す。
    expect(selection.anonymize).toBeUndefined()
  })

  it('shows the previewed markdown', async () => {
    const user = userEvent.setup()
    await renderPage()
    await user.click(previewButton())

    expect(
      await screen.findByRole('heading', { name: t('knowledgeExport.previewTitle') }),
    ).toBeTruthy()
    expect(screen.getByText(PREVIEW_MARKDOWN)).toBeTruthy()
  })

  it('sends the anonymisation flag inside the request when exporting', async () => {
    const user = userEvent.setup()
    await renderPage()
    await user.click(anonymizeCheckbox())
    await user.click(exportButton())

    await waitFor(() => expect(executeKnowledgeExport).toHaveBeenCalledOnce())
    expect(executeKnowledgeExport.mock.calls[0][1]).toMatchObject({
      anonymize: true,
      goal_overview: true,
    })
  })

  it('shows where the exported files were written', async () => {
    const user = userEvent.setup()
    await renderPage()
    await user.click(exportButton())

    expect(
      await screen.findByText(
        t('knowledgeExport.exportedPaths.markdown', { path: '/out/a.md' }),
      ),
    ).toBeTruthy()
    expect(
      screen.getByText(t('knowledgeExport.exportedPaths.json', { path: '/out/a.json' })),
    ).toBeTruthy()
  })

  it('reports that the export succeeded', async () => {
    const user = userEvent.setup()
    await renderPage()
    await user.click(exportButton())
    expect(await screen.findByText(t('knowledgeExport.exportSucceeded'))).toBeTruthy()
  })
})

describe('KnowledgeExportPage の学習サマリ', () => {
  it('shows the exam summary with the latest quality value', async () => {
    const user = userEvent.setup()
    previewKnowledgeExport.mockResolvedValue({
      markdown: PREVIEW_MARKDOWN,
      data: {
        summary: { total_minutes: 120, study_days: 4, report_rate: 0.75, replan_count: 2 },
        quality_trend: [
          { material: '教材A', cycle: 1, series: [{ date: '2026-09-12', value: 82 }] },
        ],
      },
    })
    await renderPage()
    await user.click(previewButton())

    await screen.findByRole('heading', { name: t('knowledgeExport.summary.title') })
    expect(screen.getByText('2.0')).toBeTruthy()
    expect(screen.getByText('75%')).toBeTruthy()
    expect(screen.getByText('82')).toBeTruthy()
  })

  it('marks the quality as unavailable when there is no trend', async () => {
    const user = userEvent.setup()
    previewKnowledgeExport.mockResolvedValue({
      markdown: PREVIEW_MARKDOWN,
      data: {
        summary: { total_minutes: 0, study_days: 0, report_rate: 0, replan_count: 0 },
      },
    })
    await renderPage()
    await user.click(previewButton())

    await screen.findByRole('heading', { name: t('knowledgeExport.summary.title') })
    expect(screen.getByText(t('knowledgeExport.summary.unavailable'))).toBeTruthy()
  })

  it('shows the record-days summary for a reading goal', async () => {
    const user = userEvent.setup()
    previewKnowledgeExport.mockResolvedValue({
      markdown: PREVIEW_MARKDOWN,
      data: { summary: { record_days: 12, max_streak_days: 5 } },
    })
    await renderPage({ category: 'READING' })
    await user.click(previewButton())

    await screen.findByRole('heading', { name: t('knowledgeExport.summary.readingTitle') })
    expect(screen.getByText('12')).toBeTruthy()
    expect(screen.getByText('5')).toBeTruthy()
  })

  it('shows the record-days summary for a work goal', async () => {
    const user = userEvent.setup()
    previewKnowledgeExport.mockResolvedValue({
      markdown: PREVIEW_MARKDOWN,
      data: { summary: { record_days: 12, max_streak_days: 5 } },
    })
    await renderPage({ category: 'WORK' })
    await user.click(previewButton())

    expect(
      await screen.findByRole('heading', { name: t('knowledgeExport.summary.workTitle') }),
    ).toBeTruthy()
  })

  it('hides the summary until a preview or an export produced one', async () => {
    await renderPage()
    expect(screen.queryByRole('heading', { name: t('knowledgeExport.summary.title') })).toBe(null)
  })
})

describe('KnowledgeExportPage の総括レポート', () => {
  it('shows the stored retrospective and offers regenerating it', async () => {
    await renderPage()
    expect(await screen.findByText(RETROSPECTIVE_BODY)).toBeTruthy()
    expect(
      screen.getByRole('button', { name: t('knowledgeExport.retrospective.regenerateButton') }),
    ).toBeTruthy()
  })

  it('offers generating when there is no retrospective yet', async () => {
    getRetrospective.mockResolvedValue({ body: null })
    await renderPage()
    expect(await screen.findByText(t('knowledgeExport.retrospective.empty'))).toBeTruthy()
    expect(
      screen.getByRole('button', { name: t('knowledgeExport.retrospective.generateButton') }),
    ).toBeTruthy()
  })

  it('uses the reading wording for a reading goal', async () => {
    getRetrospective.mockResolvedValue({ body: null })
    await renderPage({ category: 'READING' })
    expect(
      await screen.findByRole('heading', { name: t('knowledgeExport.retrospective.readingTitle') }),
    ).toBeTruthy()
    expect(screen.getByText(t('knowledgeExport.retrospective.readingEmpty'))).toBeTruthy()
  })

  it('generates the retrospective with the current anonymisation flag', async () => {
    const user = userEvent.setup()
    await renderPage()
    await screen.findByText(RETROSPECTIVE_BODY)
    await user.click(anonymizeCheckbox())
    await user.click(
      screen.getByRole('button', { name: t('knowledgeExport.retrospective.regenerateButton') }),
    )

    await waitFor(() => expect(generateRetrospective).toHaveBeenCalledWith(GOAL_ID, true))
  })

  it('notes that the retrospective is being generated', async () => {
    // 生成には時間がかかるため、待っていることが分かる表示に切り替える。
    const user = userEvent.setup()
    generateRetrospective.mockReturnValue(new Promise(() => undefined))
    await renderPage()
    await screen.findByText(RETROSPECTIVE_BODY)
    await user.click(
      screen.getByRole('button', { name: t('knowledgeExport.retrospective.regenerateButton') }),
    )

    expect(
      await screen.findByText(t('knowledgeExport.retrospective.generating')),
    ).toBeTruthy()
    expect(screen.queryByText(RETROSPECTIVE_BODY)).toBe(null)
  })

  it('shows a notice instead of the generator for a work goal', async () => {
    // 仕事目標は総括レポート専用エンドポイントを恒久的に使えない（データ構造編6.2）。
    await renderPage({ category: 'WORK' })
    expect(screen.getByText(t('knowledgeExport.retrospective.workNotice'))).toBeTruthy()
    expect(
      screen.queryByRole('button', { name: t('knowledgeExport.retrospective.generateButton') }),
    ).toBe(null)
    expect(getRetrospective).not.toHaveBeenCalled()
  })
})
