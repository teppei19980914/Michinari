/** useWorkReportDraft の下書き反映挙動を固定する回帰テスト。
 *
 * 従来は`report`（reportQueryの取得結果）の参照が変わるたびに無条件で`applyReport`していた
 * ため、ウィンドウ再フォーカス等によるバックグラウンドの再取得（内容は同じでも新しい
 * オブジェクト参照が返る）のたびに、入力途中（未保存）の内容が取得済みの値へ黙って
 * 巻き戻されていた（2026-09-19、下書きhydrateの調査で発覚した同根の不具合）。period_keyが
 * 変わらない限り自動反映しないよう修正したため、その境界条件を固定する。 */
import { describe, expect, it } from 'vitest'
import { act } from 'react'
import { renderHook } from '@testing-library/react'
import { makeWorkReport } from '../../test/fixtures'
import { useWorkReportDraft } from './useWorkReportDraft'
import type { WorkReportRead } from '../../api/closure'

function setup(initialReport: WorkReportRead | null | undefined) {
  return renderHook(({ report }: { report: WorkReportRead | null | undefined }) => useWorkReportDraft(report), {
    initialProps: { report: initialReport },
  })
}

describe('useWorkReportDraft', () => {
  it('fills the form from the report on first load', () => {
    const { result } = setup(makeWorkReport({ business_summary: '業務内容の要約' }))

    expect(result.current.businessSummary).toBe('業務内容の要約')
  })

  it('does not overwrite an unsaved edit when the same period is refetched in the background', () => {
    const { result, rerender } = setup(makeWorkReport({ business_summary: '業務内容の要約' }))

    act(() => {
      result.current.setBusinessSummary('編集中の下書き')
    })
    expect(result.current.businessSummary).toBe('編集中の下書き')

    // バックグラウンド再取得で内容は同じでも新しいオブジェクト参照が返る状況を再現する
    // （TanStack Queryのウィンドウ再フォーカス時の既定挙動）。
    act(() => {
      rerender({ report: makeWorkReport({ business_summary: '業務内容の要約' }) })
    })

    expect(result.current.businessSummary).toBe('編集中の下書き')
  })

  it('applies the newly loaded report when the period changes', () => {
    const { result, rerender } = setup(makeWorkReport({ period_key: '2026-08', business_summary: '8月の要約' }))

    act(() => {
      result.current.setBusinessSummary('編集中の下書き')
    })

    act(() => {
      rerender({ report: makeWorkReport({ period_key: '2026-09', business_summary: '9月の要約' }) })
    })

    expect(result.current.businessSummary).toBe('9月の要約')
  })

  it('leaves the form untouched while the report has not loaded yet or does not exist', () => {
    const { result, rerender } = setup(undefined)
    expect(result.current.businessSummary).toBe('')

    act(() => {
      rerender({ report: null })
    })
    expect(result.current.businessSummary).toBe('')
  })

  it('reflects an explicit applyReport call (generate/save) immediately', () => {
    const { result } = setup(makeWorkReport({ business_summary: '業務内容の要約' }))

    act(() => {
      result.current.applyReport(makeWorkReport({ business_summary: '再生成後の要約' }))
    })

    expect(result.current.businessSummary).toBe('再生成後の要約')
  })
})
