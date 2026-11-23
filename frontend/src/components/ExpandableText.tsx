import { useState } from 'react'
import { t } from '../locales/t'
import { isTextTruncatable } from './textTruncation'

/** 長文を改行保持で表示し、長い場合は3行で折りたたんで「続きを読む」で展開する
 * （開発Todo_単語帳_v1.0 要件F F-U10・F-D23）。単語帳の一覧・出題・今日の復習で
 * 共通して使う部品（CODING_RULES.md「①DRYの原則」）。空文字・nullは何も表示しない。
 */
export function ExpandableText({
  text,
  className = '',
}: {
  text: string | null | undefined
  className?: string
}) {
  const [expanded, setExpanded] = useState(false)

  if (!text) return null

  const truncatable = isTextTruncatable(text)
  const clamped = !expanded && truncatable

  return (
    <div className={className}>
      <p className={`whitespace-pre-wrap ${clamped ? 'line-clamp-3' : ''}`}>{text}</p>
      {truncatable && (
        <button
          type="button"
          className="mt-1 text-xs text-accent-muted-text underline"
          onClick={() => setExpanded((current) => !current)}
        >
          {expanded ? t('common.action.collapseText') : t('common.action.expandText')}
        </button>
      )}
    </div>
  )
}
