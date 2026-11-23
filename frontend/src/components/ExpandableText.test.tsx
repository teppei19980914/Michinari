import { describe, expect, it } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import { t } from '../locales/t'
import { ExpandableText } from './ExpandableText'

describe('ExpandableText', () => {
  it('renders nothing for empty text', () => {
    const { container } = render(<ExpandableText text={null} />)
    expect(container.textContent).toBe('')
  })

  it('shows short text without a toggle button', () => {
    render(<ExpandableText text="短い文" />)

    expect(screen.getByText('短い文')).toBeTruthy()
    expect(screen.queryByText(t('common.action.expandText'))).toBeNull()
  })

  it('shows a toggle button for long text and expands/collapses on click', () => {
    const longText = '1行目\n2行目\n3行目\n4行目'
    render(<ExpandableText text={longText} />)

    expect(screen.getByText(t('common.action.expandText'))).toBeTruthy()

    fireEvent.click(screen.getByText(t('common.action.expandText')))
    expect(screen.getByText(t('common.action.collapseText'))).toBeTruthy()

    fireEvent.click(screen.getByText(t('common.action.collapseText')))
    expect(screen.getByText(t('common.action.expandText'))).toBeTruthy()
  })
})
