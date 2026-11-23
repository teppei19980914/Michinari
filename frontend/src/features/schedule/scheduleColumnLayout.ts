import type { CSSProperties } from 'react'

/**
 * スケジュールタブの列幅・固定列のsticky left位置を算出する（開発Todo_スケジュール・
 * ガントチャート_v1.1 D-08・D-13・D-15・D-24・D-25、3.2）。
 *
 * 列幅は利用者による変更の対象外（D-15）のため、固定のrem値として持つ。行操作列は常に
 * 左端に固定し、固定する列数（`frozen_column_count`）には数えない（3.2、閲覧のみの目標では
 * 表示しない）。既定7列は常に左から固定の順で並び、追加列はその右側に続く。
 */

/** 固定列・固定行のsticky style（セル側・見出し側の両方で使う共通関数、DRYの原則）。
 * 見出し行は本文より上に重なる必要があるため`zIndex`を高くする（既定1、見出しは2）。 */
export function stickyStyle(leftRem: number | null, zIndex: 1 | 2 = 1): CSSProperties {
  return leftRem === null ? {} : { position: 'sticky', left: `${leftRem}rem`, zIndex }
}

export const DEFAULT_COLUMN_KEYS = [
  'title',
  'description',
  'plannedStartDate',
  'plannedEndDate',
  'status',
  'actualStartDate',
  'actualEndDate',
] as const

export type DefaultColumnKey = (typeof DEFAULT_COLUMN_KEYS)[number]

//: 既定7列の幅（rem）。日付列は"2026-11-23"相当の date input が収まる幅、状況列は
//: 選択肢の最長文言（"未着手"等）が収まる幅とした（影響範囲確定時の実装詳細）。
export const DEFAULT_COLUMN_WIDTH_REM: Record<DefaultColumnKey, number> = {
  title: 10,
  description: 12,
  plannedStartDate: 7.5,
  plannedEndDate: 7.5,
  status: 6.5,
  actualStartDate: 7.5,
  actualEndDate: 7.5,
}

//: 追加列（テキスト型のみ、D-12）の幅。
export const CUSTOM_COLUMN_WIDTH_REM = 8

//: 行操作列（上へ・下へ・下に挿入・削除）の幅。常に左端固定、固定列数には数えない。
export const ROW_ACTIONS_WIDTH_REM = 4.5

/** 既定7列＋追加列N列の幅の配列（rem、左から並び順どおり）を返す。 */
export function buildColumnWidthsRem(customColumnCount: number): number[] {
  const defaults = DEFAULT_COLUMN_KEYS.map((key) => DEFAULT_COLUMN_WIDTH_REM[key])
  const customs = Array.from({ length: Math.max(0, customColumnCount) }, () => CUSTOM_COLUMN_WIDTH_REM)
  return [...defaults, ...customs]
}

/** 行操作列＋既定7列＋追加列N列の合計幅（rem）。ガント領域の左端位置・利用可能幅の算出に使う。 */
export function totalFixedAreaWidthRem(customColumnCount: number, showRowActions: boolean): number {
  const columnsWidth = buildColumnWidthsRem(customColumnCount).reduce((sum, width) => sum + width, 0)
  return columnsWidth + (showRowActions ? ROW_ACTIONS_WIDTH_REM : 0)
}

/**
 * 行操作列＋固定するfrozenColumnCount列について、sticky用のleft位置（rem）を列の並び順で
 * 返す。固定しない列（並び順でfrozenColumnCount以降）はnullを返す。行操作列は
 * `showRowActions`がfalse（閲覧のみの目標）なら配列に含めない。
 */
export function computeStickyLeftOffsetsRem(
  customColumnCount: number,
  frozenColumnCount: number,
  showRowActions: boolean,
): { rowActionsLeftRem: number | null; columnLeftOffsetsRem: (number | null)[] } {
  const widths = buildColumnWidthsRem(customColumnCount)
  const rowActionsLeftRem = showRowActions ? 0 : null
  let cursor = showRowActions ? ROW_ACTIONS_WIDTH_REM : 0

  const columnLeftOffsetsRem = widths.map((width, index) => {
    if (index >= frozenColumnCount) {
      return null
    }
    const left = cursor
    cursor += width
    return left
  })

  return { rowActionsLeftRem, columnLeftOffsetsRem }
}
