import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ScheduleDateCell } from './ScheduleDateCell'

const onChange = vi.fn()

beforeEach(() => {
  vi.clearAllMocks()
})

afterEach(() => {
  cleanup()
})

describe('ScheduleDateCell', () => {
  it('値をそのまま表示する', () => {
    render(
      <ScheduleDateCell
        label="予定開始日"
        value="2026-11-01"
        disabled={false}
        hasError={false}
        widthRem={7.5}
        leftRem={null}
        onChange={onChange}
      />,
    )
    const input = screen.getByLabelText('予定開始日') as HTMLInputElement
    expect(input.value).toBe('2026-11-01')
  })

  it('値が無い場合は空欄で表示する', () => {
    render(
      <ScheduleDateCell
        label="実績開始日"
        value={null}
        disabled={false}
        hasError={false}
        widthRem={7.5}
        leftRem={null}
        onChange={onChange}
      />,
    )
    expect((screen.getByLabelText('実績開始日') as HTMLInputElement).value).toBe('')
  })

  it('変更するとonChangeへ値を渡す。空欄に戻した場合はnullを渡す', async () => {
    render(
      <ScheduleDateCell
        label="実績開始日"
        value="2026-11-01"
        disabled={false}
        hasError={false}
        widthRem={7.5}
        leftRem={null}
        onChange={onChange}
      />,
    )
    const input = screen.getByLabelText('実績開始日')
    await userEvent.clear(input)
    expect(onChange).toHaveBeenLastCalledWith(null)
  })

  it('leftRemを指定すると固定表示のスタイルを付ける', () => {
    const { container } = render(
      <ScheduleDateCell
        label="予定開始日"
        value="2026-11-01"
        disabled={false}
        hasError={false}
        widthRem={7.5}
        leftRem={4.5}
        onChange={onChange}
      />,
    )
    expect((container.firstChild as HTMLElement).style.position).toBe('sticky')
    expect((container.firstChild as HTMLElement).style.left).toBe('4.5rem')
  })

  it('hasErrorのときは赤枠のクラスを付ける', () => {
    render(
      <ScheduleDateCell
        label="予定開始日"
        value="2026-11-01"
        disabled={false}
        hasError={true}
        widthRem={7.5}
        leftRem={null}
        onChange={onChange}
      />,
    )
    expect((screen.getByLabelText('予定開始日') as HTMLInputElement).className).toContain(
      'border-danger-text',
    )
  })

  it('disabledを伝える', () => {
    render(
      <ScheduleDateCell
        label="実績開始日"
        value={null}
        disabled={true}
        hasError={false}
        widthRem={7.5}
        leftRem={null}
        onChange={onChange}
      />,
    )
    expect((screen.getByLabelText('実績開始日') as HTMLInputElement).disabled).toBe(true)
  })
})
