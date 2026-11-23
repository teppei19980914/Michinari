import { describe, expect, it } from 'vitest'
import {
  CUSTOM_COLUMN_WIDTH_REM,
  DEFAULT_COLUMN_WIDTH_REM,
  ROW_ACTIONS_WIDTH_REM,
  buildColumnWidthsRem,
  computeStickyLeftOffsetsRem,
  stickyStyle,
  totalFixedAreaWidthRem,
} from './scheduleColumnLayout'

describe('stickyStyle', () => {
  it('leftRemがnullならstyleを付けない', () => {
    expect(stickyStyle(null)).toEqual({})
  })

  it('leftRemを指定するとposition: stickyと既定のzIndex(1)を付ける', () => {
    expect(stickyStyle(4.5)).toEqual({ position: 'sticky', left: '4.5rem', zIndex: 1 })
  })

  it('zIndexを指定すると（見出し用の2等）その値を使う', () => {
    expect(stickyStyle(0, 2)).toEqual({ position: 'sticky', left: '0rem', zIndex: 2 })
  })
})

describe('buildColumnWidthsRem', () => {
  it('追加列が0件なら既定7列分の幅のみを返す', () => {
    expect(buildColumnWidthsRem(0)).toHaveLength(7)
  })

  it('追加列N件分の幅を既定7列の後ろに追加する', () => {
    const widths = buildColumnWidthsRem(3)
    expect(widths).toHaveLength(10)
    expect(widths.slice(7)).toEqual([
      CUSTOM_COLUMN_WIDTH_REM,
      CUSTOM_COLUMN_WIDTH_REM,
      CUSTOM_COLUMN_WIDTH_REM,
    ])
  })
})

describe('totalFixedAreaWidthRem', () => {
  it('行操作列を含めた既定7列の合計幅を返す', () => {
    const widths = buildColumnWidthsRem(0)
    const expected = widths.reduce((sum, width) => sum + width, 0) + ROW_ACTIONS_WIDTH_REM
    expect(totalFixedAreaWidthRem(0, true)).toBeCloseTo(expected)
  })

  it('閲覧のみの目標（行操作列を表示しない）は行操作列の幅を含めない', () => {
    const widths = buildColumnWidthsRem(0)
    const expected = widths.reduce((sum, width) => sum + width, 0)
    expect(totalFixedAreaWidthRem(0, false)).toBeCloseTo(expected)
  })

  it('追加列の幅も加算する', () => {
    expect(totalFixedAreaWidthRem(2, true)).toBeCloseTo(totalFixedAreaWidthRem(0, true) + 2 * CUSTOM_COLUMN_WIDTH_REM)
  })
})

describe('computeStickyLeftOffsetsRem', () => {
  it('固定行操作列を表示し、固定列数0なら既定列はすべてnull', () => {
    const { rowActionsLeftRem, columnLeftOffsetsRem } = computeStickyLeftOffsetsRem(0, 0, true)
    expect(rowActionsLeftRem).toBe(0)
    expect(columnLeftOffsetsRem).toEqual(Array(7).fill(null))
  })

  it('固定列数1（既定の作業項目列のみ）なら、行操作列の幅の後ろに作業項目列が来る', () => {
    const { rowActionsLeftRem, columnLeftOffsetsRem } = computeStickyLeftOffsetsRem(0, 1, true)
    expect(rowActionsLeftRem).toBe(0)
    expect(columnLeftOffsetsRem[0]).toBe(ROW_ACTIONS_WIDTH_REM)
    expect(columnLeftOffsetsRem[1]).toBeNull()
  })

  it('固定列数2なら2列目は作業項目列の幅の分だけ右に来る', () => {
    const { columnLeftOffsetsRem } = computeStickyLeftOffsetsRem(0, 2, true)
    expect(columnLeftOffsetsRem[0]).toBe(ROW_ACTIONS_WIDTH_REM)
    expect(columnLeftOffsetsRem[1]).toBe(ROW_ACTIONS_WIDTH_REM + DEFAULT_COLUMN_WIDTH_REM.title)
    expect(columnLeftOffsetsRem[2]).toBeNull()
  })

  it('閲覧のみの目標（showRowActions=false）では行操作列の幅を計算に含めない', () => {
    const { rowActionsLeftRem, columnLeftOffsetsRem } = computeStickyLeftOffsetsRem(0, 1, false)
    expect(rowActionsLeftRem).toBeNull()
    expect(columnLeftOffsetsRem[0]).toBe(0)
  })

  it('固定列数が追加列にまで及ぶ場合、追加列のleft位置も算出する', () => {
    const { columnLeftOffsetsRem } = computeStickyLeftOffsetsRem(2, 9, true)
    // 行操作列 + 既定7列 + 追加列2列 = 固定列数9（追加列まで全て固定）
    expect(columnLeftOffsetsRem).toHaveLength(9)
    expect(columnLeftOffsetsRem.every((offset) => offset !== null)).toBe(true)
  })
})
