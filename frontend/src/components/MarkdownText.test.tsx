/** MarkdownTextの配色クラスを固定する。`dark:prose-invert`が無いと、ダークモードで
 * `prose-gray`のライト専用固定色が残り、暗い背景と同化して読めなくなる不具合が
 * 2026-10利用者検証で見つかった（MarkdownText.tsxの先頭コメント参照）。 */
import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MarkdownText } from './MarkdownText'

describe('MarkdownText', () => {
  it('renders the markdown body', () => {
    render(<MarkdownText text="**重要**な連絡です" className="text-text-primary" />)

    expect(screen.getByText('重要')).toBeDefined()
    expect(screen.getByText('な連絡です', { exact: false })).toBeDefined()
  })

  it('inverts the prose color scheme in dark mode so the text does not blend into the background', () => {
    const { container } = render(<MarkdownText text="本文" className="text-text-primary" />)

    const wrapper = container.firstElementChild
    expect(wrapper?.className).toContain('dark:prose-invert')
  })

  it('appends the caller-provided className alongside the prose classes', () => {
    const { container } = render(<MarkdownText text="本文" className="text-sm text-text-primary" />)

    const wrapper = container.firstElementChild
    expect(wrapper?.className).toContain('text-sm')
    expect(wrapper?.className).toContain('text-text-primary')
  })
})
