/** ブラウザへファイルをダウンロードさせる共通処理（CLAUDE.md DRYの原則。
 * DataManagementPageのエクスポート、月次報告・半期評価のMarkdownダウンロード
 * （実装フェーズ分割計画書Phase23）の双方から使う）。 */
export function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  anchor.click()
  URL.revokeObjectURL(url)
}
