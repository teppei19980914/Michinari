import ja from './ja.json'
import en from './en.json'

/** 対応言語（`app_setting.display.locale`と同じ値、settings_service._ALLOWED_LOCALES参照）。 */
export type Locale = 'ja' | 'en'

const MESSAGES: Record<Locale, unknown> = { ja, en }

/** 現在のロケール。起動時に`setLocale()`で一度確定させ、以降は`main.tsx`のブートストラップ
 * を経由した再読込でのみ変わる想定（画面内での動的切替は行わない）。 */
let currentLocale: Locale = 'ja'

export function setLocale(locale: Locale): void {
  currentLocale = locale
}

export function getLocale(): Locale {
  return currentLocale
}

/** APIから受け取った`locale`文字列が対応言語かを判定する（`settings_service._ALLOWED_LOCALES`
 * と同じ値のみ許容。未知の値が来た場合は呼び出し側で既定のjaへフォールバックさせる）。 */
export function isLocale(value: string): value is Locale {
  return value === 'ja' || value === 'en'
}

/** 単数/複数で語形が変わる言語（英語）向けの値。日本語は語形変化が無いため文字列のまま。 */
type PluralValue = { one?: string; other: string }

function isPluralValue(value: unknown): value is PluralValue {
  return (
    typeof value === 'object' &&
    value !== null &&
    typeof (value as Record<string, unknown>).other === 'string'
  )
}

/**
 * ドット区切りキーでロケール文言を取得する（CODING_RULES.md「ロケールキー」）。
 * 外部i18nライブラリは導入しない（技術選定書に記載なし。日英2言語を自前の仕組みで解決する）。
 */
export function t(key: string, vars?: Record<string, string | number>): string {
  const value = key
    .split('.')
    .reduce<unknown>(
      (node, part) => (typeof node === 'object' && node !== null ? (node as Record<string, unknown>)[part] : undefined),
      MESSAGES[currentLocale],
    )

  let text: string
  if (typeof value === 'string') {
    text = value
  } else if (isPluralValue(value)) {
    const isSingular = vars !== undefined && Number(vars.count) === 1
    text = isSingular && typeof value.one === 'string' ? value.one : value.other
  } else {
    return key
  }

  if (!vars) {
    return text
  }
  return Object.entries(vars).reduce(
    (acc, [name, replacement]) => acc.replaceAll(`{{${name}}}`, String(replacement)),
    text,
  )
}
