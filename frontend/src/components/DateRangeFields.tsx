import { Input } from './Input'

export type DateRangeFieldsProps = {
  dateFrom: string
  dateTo: string
  fromLabel: string
  toLabel: string
  onChangeFrom: (value: string) => void
  onChangeTo: (value: string) => void
}

/** 開始日・終了日の2つの日付入力（`min`/`max`で互いの範囲を制約する）。`LogExportSection.tsx`
 * （SC-15 診断ログ）・`SummaryCardSection.tsx`（ふりかえりまとめ・共有カード）で同型の
 * マークアップが2箇所あったため共通化した（DRYレビュー指摘、2026-11-13。CODING_RULES.md
 * ①DRYの原則）。ラベル文言は呼び出し側がロケールから渡す（ゼロハードコーディング）。 */
export function DateRangeFields({
  dateFrom,
  dateTo,
  fromLabel,
  toLabel,
  onChangeFrom,
  onChangeTo,
}: DateRangeFieldsProps) {
  return (
    <>
      <label className="flex flex-col gap-1 text-sm text-text-secondary">
        {fromLabel}
        <Input
          type="date"
          value={dateFrom}
          max={dateTo}
          onChange={(e) => onChangeFrom(e.target.value)}
        />
      </label>
      <label className="flex flex-col gap-1 text-sm text-text-secondary">
        {toLabel}
        <Input
          type="date"
          value={dateTo}
          min={dateFrom}
          onChange={(e) => onChangeTo(e.target.value)}
        />
      </label>
    </>
  )
}
