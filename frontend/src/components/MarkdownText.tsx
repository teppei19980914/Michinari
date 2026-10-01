import ReactMarkdown from 'react-markdown'

type MarkdownTextProps = {
  text: string
  className: string
}

/** AI生成テキスト（先週のまとめ・総括レポート等、見出し・箇条書き・強調を含む構造的な文書
 * として生成されるもの）をマークダウンとしてプレビュー表示する共通部品。
 *
 * rehype-rawは導入せず生HTMLをパースしないため、AI生成テキストに悪意あるHTML/スクリプトが
 * 含まれてもXSSにはならない（react-markdownの既定挙動）。 */
export function MarkdownText({ text, className }: MarkdownTextProps) {
  return (
    <div className={`prose prose-sm prose-gray max-w-none ${className}`}>
      <ReactMarkdown>{text}</ReactMarkdown>
    </div>
  )
}
