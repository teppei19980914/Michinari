import ja from './ja.json'

/**
 * ドット区切りキーでロケール文言を取得する（CODING_RULES.md「ロケールキー」）。
 * 外部i18nライブラリは導入しない（技術選定書に記載なし。表示言語は日本語のみを対象とする）。
 */
export function t(key: string, vars?: Record<string, string | number>): string {
  const value = key
    .split('.')
    .reduce<unknown>((node, part) => (typeof node === 'object' && node !== null ? (node as Record<string, unknown>)[part] : undefined), ja)

  if (typeof value !== 'string') {
    return key
  }
  if (!vars) {
    return value
  }
  return Object.entries(vars).reduce(
    (text, [name, replacement]) => text.replaceAll(`{{${name}}}`, String(replacement)),
    value,
  )
}
