import { describe, expect, it } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import { CollapsibleSection } from './CollapsibleSection'

describe('CollapsibleSection', () => {
  it('hides the children and shows the show-label by default', () => {
    render(
      <CollapsibleSection title="詳細設定を表示" hiddenTitle="詳細設定を隠す">
        <p>中身</p>
      </CollapsibleSection>,
    )

    expect(screen.getByText('詳細設定を表示')).toBeTruthy()
    expect(screen.queryByText('中身')).toBeNull()
  })

  it('reveals the children and swaps to the hide-label after a click', () => {
    render(
      <CollapsibleSection title="詳細設定を表示" hiddenTitle="詳細設定を隠す">
        <p>中身</p>
      </CollapsibleSection>,
    )

    fireEvent.click(screen.getByText('詳細設定を表示'))

    expect(screen.getByText('中身')).toBeTruthy()
    expect(screen.getByText('詳細設定を隠す')).toBeTruthy()
  })

  it('collapses again after a second click', () => {
    render(
      <CollapsibleSection title="詳細設定を表示" hiddenTitle="詳細設定を隠す">
        <p>中身</p>
      </CollapsibleSection>,
    )

    fireEvent.click(screen.getByText('詳細設定を表示'))
    fireEvent.click(screen.getByText('詳細設定を隠す'))

    expect(screen.queryByText('中身')).toBeNull()
  })

  it('starts open when defaultOpen is true', () => {
    render(
      <CollapsibleSection title="詳細設定を表示" hiddenTitle="詳細設定を隠す" defaultOpen>
        <p>中身</p>
      </CollapsibleSection>,
    )

    expect(screen.getByText('中身')).toBeTruthy()
  })
})
