import type { ReactNode } from 'react'

export type TooltipPosition = 'above' | 'below'

/**
 * ホバー時に説明文を吹き出し表示する（CSSのみ、JS状態を持たない）。
 * `position`省略時は既定の`'above'`（トリガーの上に表示、既存の全呼び出し元の見た目を
 * 変えない）。スケジュールタブのガント帯（開発Todo_スケジュール・ガントチャート_v1.1
 * D-27）は帯の真上に表示領域が無い場合があるため`'below'`を使う。
 */
export function Tooltip({
  label,
  children,
  position = 'above',
  wrapperClassName = '',
}: {
  label: string
  children: ReactNode
  position?: TooltipPosition
  /** トリガー自身のラップ用span（既定`inline-flex`）へ追加するクラス。スケジュール
   * タブのガント帯（行全体をホバー対象にする）のように、既定の`inline-flex`では
   * 大きさが合わない場合に使う（既存の呼び出し元は省略のため見た目は変わらない）。 */
  wrapperClassName?: string
}) {
  const positionClassName = position === 'above' ? 'bottom-full mb-2' : 'top-full mt-2'
  return (
    <span className={`group relative inline-flex ${wrapperClassName}`}>
      {children}
      <span
        role="tooltip"
        className={`pointer-events-none absolute left-1/2 z-10 w-64 -translate-x-1/2 rounded-md bg-overlay-strong px-3 py-2 text-xs leading-relaxed text-white opacity-0 shadow-lg transition-opacity duration-150 group-hover:opacity-100 ${positionClassName}`}
      >
        {label}
      </span>
    </span>
  )
}
