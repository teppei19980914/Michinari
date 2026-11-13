/** ふりかえりまとめ・共有カード（開発Todo「まとめと共有カード」v1.0）。
 *
 * 期間指定モード（mode: 'open'）・目標完了時モード（mode: 'fixed'）の両方、表示トグル、
 * AI一文生成の有無、PNG保存・クリップボードコピーの成功/失敗/非対応環境を固定する。 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { t } from '../../locales/t'
import { renderWithProviders } from '../../test/renderWithProviders'
import { SummaryCardSection } from './SummaryCardSection'

const getToday = vi.hoisted(() => vi.fn())
vi.mock('../../api/records', () => ({ getToday }))

const getAiStatus = vi.hoisted(() => vi.fn())
vi.mock('../../api/ai', () => ({ getAiStatus }))

const getSummaryCard = vi.hoisted(() => vi.fn())
const generateSummaryCardSentence = vi.hoisted(() => vi.fn())
vi.mock('../../api/summaryCard', () => ({ getSummaryCard, generateSummaryCardSentence }))

const downloadBlob = vi.hoisted(() => vi.fn())
vi.mock('../../utils/downloadBlob', () => ({ downloadBlob }))

const svgElementToPngBlob = vi.hoisted(() => vi.fn())
const copyPngBlobToClipboard = vi.hoisted(() => vi.fn())
const isClipboardImageCopySupported = vi.hoisted(() => vi.fn())
vi.mock('./summaryCardImage', () => ({
  svgElementToPngBlob,
  copyPngBlobToClipboard,
  isClipboardImageCopySupported,
}))

const TODAY = '2026-11-13'
const AGGREGATE = {
  record_days: 10,
  longest_consecutive_days: 5,
  top_theme_name: '過去問演習',
  milestones: [],
  roadmap: { progress_ratio: 0.5, is_achieved: false, overrun_days: null },
}
const PNG_BLOB = new Blob(['png'], { type: 'image/png' })

const generateSentenceButton = () =>
  screen.getByRole('button', { name: t('summaryCard.generateSentenceButton') })
const saveButton = () => screen.getByRole('button', { name: t('summaryCard.saveButton') })
const copyButton = () => screen.getByRole('button', { name: t('summaryCard.copyButton') })

beforeEach(() => {
  vi.clearAllMocks()
  getToday.mockResolvedValue({ logical_date: TODAY, record_state: null })
  getAiStatus.mockResolvedValue({ authenticated: true, model_status: {}, login_in_progress: false })
  getSummaryCard.mockResolvedValue(AGGREGATE)
  generateSummaryCardSentence.mockResolvedValue({ sentence: 'よく続けられました' })
  svgElementToPngBlob.mockResolvedValue(PNG_BLOB)
  copyPngBlobToClipboard.mockResolvedValue(undefined)
  isClipboardImageCopySupported.mockReturnValue(true)
})

afterEach(() => {
  cleanup()
})

describe('期間指定モード（mode: "open"）', () => {
  it('サーバの論理日から既定期間（当年1/1〜論理日）を算出し、集計を取得する', async () => {
    renderWithProviders(<SummaryCardSection goalId={1} goalName="基本情報技術者試験" category="EXAM" mode="open" />)

    await waitFor(() => expect(getSummaryCard).toHaveBeenCalledWith(1, '2026-01-01', TODAY))
    expect(await screen.findByText(t('summaryCard.unit.days', { count: 10 }))).toBeTruthy()
  })

  it('「今年」ボタンで既定期間に戻せる', async () => {
    const user = userEvent.setup()
    renderWithProviders(<SummaryCardSection goalId={1} goalName="目標" category="EXAM" mode="open" />)
    await waitFor(() => expect(getSummaryCard).toHaveBeenCalledTimes(1))

    await user.click(screen.getByRole('button', { name: t('summaryCard.periodPresetThisYear') }))
    await waitFor(() => expect(getSummaryCard).toHaveBeenCalledWith(1, '2026-01-01', TODAY))
  })

  it('開始日を変更すると、その期間で再取得する', async () => {
    renderWithProviders(<SummaryCardSection goalId={1} goalName="目標" category="EXAM" mode="open" />)
    await waitFor(() => expect(getSummaryCard).toHaveBeenCalledTimes(1))

    const fromInput = screen.getByLabelText(t('summaryCard.periodFromLabel'))
    fireEvent.change(fromInput, { target: { value: '2026-06-01' } })

    await waitFor(() => expect(getSummaryCard).toHaveBeenCalledWith(1, '2026-06-01', TODAY))
  })

  it('終了日を変更すると、その期間で再取得する', async () => {
    renderWithProviders(<SummaryCardSection goalId={1} goalName="目標" category="EXAM" mode="open" />)
    await waitFor(() => expect(getSummaryCard).toHaveBeenCalledTimes(1))

    const toInput = screen.getByLabelText(t('summaryCard.periodToLabel'))
    fireEvent.change(toInput, { target: { value: '2026-11-01' } })

    await waitFor(() => expect(getSummaryCard).toHaveBeenCalledWith(1, '2026-01-01', '2026-11-01'))
  })
})

describe('目標完了時モード（mode: "fixed"）', () => {
  it('固定期間を使い、期間の案内文を出す（編集UIは出さない）', async () => {
    renderWithProviders(
      <SummaryCardSection
        goalId={1}
        goalName="目標"
        category="EXAM"
        mode="fixed"
        fixedPeriod={{ dateFrom: '2026-01-01', dateTo: '2026-10-20' }}
      />,
    )

    expect(await screen.findByText(t('summaryCard.fixedPeriodNote'))).toBeTruthy()
    expect(getSummaryCard).toHaveBeenCalledWith(1, '2026-01-01', '2026-10-20')
    expect(screen.queryByLabelText(t('summaryCard.periodFromLabel'))).toBeNull()
    expect(getToday).not.toHaveBeenCalled()
  })
})

describe('集計取得エラー', () => {
  it('取得に失敗した場合はエラーメッセージを表示する', async () => {
    getSummaryCard.mockRejectedValue(new Error('boom'))
    renderWithProviders(
      <SummaryCardSection
        goalId={1}
        goalName="目標"
        category="EXAM"
        mode="fixed"
        fixedPeriod={{ dateFrom: '2026-01-01', dateTo: '2026-10-20' }}
      />,
    )

    expect(await screen.findByText(t('errors.default'))).toBeTruthy()
  })
})

describe('表示トグル', () => {
  it('チェックを外すと、カード上の当該項目が消える', async () => {
    const user = userEvent.setup()
    renderWithProviders(
      <SummaryCardSection
        goalId={1}
        goalName="目標"
        category="EXAM"
        mode="fixed"
        fixedPeriod={{ dateFrom: '2026-01-01', dateTo: '2026-10-20' }}
      />,
    )
    await screen.findByText(t('summaryCard.unit.days', { count: 10 }))

    await user.click(screen.getByRole('checkbox', { name: t('summaryCard.labels.recordDays') }))

    expect(screen.queryByText(t('summaryCard.unit.days', { count: 10 }))).toBeNull()
  })
})

describe('AI一文の生成', () => {
  it('AI設定済みなら生成ボタンを押すとAPIを呼び、一文を表示する', async () => {
    const user = userEvent.setup()
    renderWithProviders(
      <SummaryCardSection
        goalId={1}
        goalName="目標"
        category="EXAM"
        mode="fixed"
        fixedPeriod={{ dateFrom: '2026-01-01', dateTo: '2026-10-20' }}
      />,
    )
    await screen.findByText(t('summaryCard.unit.days', { count: 10 }))

    await user.click(generateSentenceButton())

    expect(generateSummaryCardSentence).toHaveBeenCalledWith(1, '2026-01-01', '2026-10-20')
    expect(await screen.findByText('よく続けられました')).toBeTruthy()
  })

  it('AI未設定なら生成ボタンを出さず、案内を表示する', async () => {
    getAiStatus.mockResolvedValue({ authenticated: false, model_status: {}, login_in_progress: false })
    renderWithProviders(
      <SummaryCardSection
        goalId={1}
        goalName="目標"
        category="EXAM"
        mode="fixed"
        fixedPeriod={{ dateFrom: '2026-01-01', dateTo: '2026-10-20' }}
      />,
    )
    await screen.findByText(t('summaryCard.unit.days', { count: 10 }))

    expect(screen.queryByRole('button', { name: t('summaryCard.generateSentenceButton') })).toBeNull()
    expect(screen.getByText(t('aiUnconfigured.message'))).toBeTruthy()
  })
})

describe('保存・コピー', () => {
  async function renderFixed() {
    const result = renderWithProviders(
      <SummaryCardSection
        goalId={1}
        goalName="目標"
        category="EXAM"
        mode="fixed"
        fixedPeriod={{ dateFrom: '2026-01-01', dateTo: '2026-10-20' }}
      />,
    )
    await screen.findByText(t('summaryCard.unit.days', { count: 10 }))
    return result
  }

  it('保存ボタンはPNGへ変換してダウンロードさせる', async () => {
    const user = userEvent.setup()
    await renderFixed()

    await user.click(saveButton())

    await waitFor(() => expect(svgElementToPngBlob).toHaveBeenCalledOnce())
    expect(downloadBlob).toHaveBeenCalledWith(
      PNG_BLOB,
      'michinari-summary-card_2026-01-01_2026-10-20.png',
    )
    expect(await screen.findByText(t('summaryCard.saveSucceeded'))).toBeTruthy()
  })

  it('保存に失敗した場合はエラーを表示する', async () => {
    svgElementToPngBlob.mockRejectedValue(new Error('boom'))
    const user = userEvent.setup()
    await renderFixed()

    await user.click(saveButton())

    expect(await screen.findByText(t('errors.default'))).toBeTruthy()
  })

  it('コピーボタンはPNGへ変換してクリップボードへコピーする', async () => {
    const user = userEvent.setup()
    await renderFixed()

    await user.click(copyButton())

    await waitFor(() => expect(copyPngBlobToClipboard).toHaveBeenCalledWith(PNG_BLOB))
    expect(await screen.findByText(t('summaryCard.copySucceeded'))).toBeTruthy()
  })

  it('非対応環境ではコピーボタンを無効化し、案内を表示する', async () => {
    isClipboardImageCopySupported.mockReturnValue(false)
    await renderFixed()

    expect((copyButton() as HTMLButtonElement).disabled).toBe(true)
    expect(screen.getByText(t('summaryCard.copyUnsupportedNote'))).toBeTruthy()
  })
})
