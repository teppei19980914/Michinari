/** 画面全体の予期しない描画エラーへの最終防波堤（非エンジニア向けエラー表示改善）。
 * これが無いと真っ白な画面のまま止まる不具合を防ぐ。 */
import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import { t } from '../locales/t'
import { ErrorBoundary } from './ErrorBoundary'

function Bomb(): never {
  throw new Error('boom')
}

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

describe('ErrorBoundary', () => {
  it('renders children normally when nothing throws', () => {
    render(
      <ErrorBoundary>
        <p>ok-content</p>
      </ErrorBoundary>,
    )

    expect(screen.getByText('ok-content')).toBeTruthy()
  })

  it('shows a plain-language message and a foldable technical detail when a child throws', () => {
    // Reactは描画時例外をconsole.errorへも出すため、テスト出力を汚さないよう黙らせる。
    vi.spyOn(console, 'error').mockImplementation(() => undefined)

    render(
      <ErrorBoundary>
        <Bomb />
      </ErrorBoundary>,
    )

    expect(screen.getByText(t('errorBoundary.message'))).toBeTruthy()
    const summary = screen.getByText(t('errorBoundary.detailsSummary'))
    expect(summary.closest('details')).not.toBe(null)
    expect(screen.getByText('boom')).toBeTruthy()
  })
})
