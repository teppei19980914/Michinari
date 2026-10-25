import ReactMarkdown from 'react-markdown'

type MarkdownTextProps = {
  text: string
  className: string
}

/** AI生成テキスト（先週のまとめ・総括レポート等、見出し・箇条書き・強調を含む構造的な文書
 * として生成されるもの）をマークダウンとしてプレビュー表示する共通部品。
 *
 * rehype-rawは導入せず生HTMLをパースしないため、AI生成テキストに悪意あるHTML/スクリプトが
 * 含まれてもXSSにはならない（react-markdownの既定挙動）。
 *
 * `prose-gray`は本文・見出し等の文字色をライトモード専用の固定値で直接指定するため、
 * `dark:prose-invert`が無いとダークモードでも暗い文字色のまま残り、暗い背景と同化して
 * 読めなくなる（2026-10利用者検証で発覚。Tailwind Typography公式のダークモード対応）。 */
export function MarkdownText({ text, className }: MarkdownTextProps) {
  return (
    <div className={`prose prose-sm prose-gray max-w-none dark:prose-invert ${className}`}>
      <ReactMarkdown>{text}</ReactMarkdown>
    </div>
  )
}
