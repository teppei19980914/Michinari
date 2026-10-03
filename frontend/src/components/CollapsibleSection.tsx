import { useState, type ReactNode } from 'react'

/** 既定で折りたたんだ領域（仕様書「上級設定の折りたたみ」）。
 *
 * このリポジトリに折りたたみUIの前例が無いため新規に用意した汎用部品。文言はローカライズ済みの
 * 状態でtitle/hiddenTitleとして呼び出し側から渡す（ゼロハードコーディング。CODING_RULES.md）。 */
export function CollapsibleSection({
  title,
  hiddenTitle,
  defaultOpen = false,
  children,
}: {
  title: string
  hiddenTitle: string
  defaultOpen?: boolean
  children: ReactNode
}) {
  const [open, setOpen] = useState(defaultOpen)

  return (
    <div>
      <button
        type="button"
        className="text-sm font-medium text-blue-600 hover:underline"
        aria-expanded={open}
        onClick={() => setOpen((prev) => !prev)}
      >
        {open ? hiddenTitle : title}
      </button>
      {open && <div className="mt-2">{children}</div>}
    </div>
  )
}
