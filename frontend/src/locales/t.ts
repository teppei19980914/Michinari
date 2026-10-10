import ja from './ja.json'
import en from './en.json'

/**
 * 日英i18n対応（2026-10）の中心モジュール。現在ロケールの保持（`setLocale`/`getLocale`）、
 * ドット区切りキーの文言解決（`t`）、単数/複数形の分岐、ロケール依存の区切り記号・
 * `Intl`/`toLocaleString`向けロケールタグの提供をまとめて担う。外部i18nライブラリは
 * 導入しない（技術選定書に記載なし。日英2言語を自前の仕組みで解決する）。
 */

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

/** 日付範囲（「3/2〜3/8」等）をつなぐ区切り記号。文章ではなく表示上の記号のため
 * ja.json/en.jsonでは管理しない（label-checkerレビューで対象外と判定済み、2026-10）。
 * 呼び出し元ごとに同じ三項演算子を書くとDRY違反になるため、ここに集約する。 */
export function rangeSeparator(): string {
  return currentLocale === 'en' ? '–' : '〜'
}

/** `Date.prototype.toLocaleString`等、`Intl`が要求するBCP47ロケールタグ。ユーザーに見える
 * 文言ではないためja.json/en.json管理の対象外（同上）。呼び出し元ごとの重複を避けるため
 * ここに集約する。 */
export function dateTimeLocaleTag(): string {
  return currentLocale === 'en' ? 'en-US' : 'ja-JP'
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

/** 単数/複数の分岐に使う数量を`vars`から決める。呼び出し元に`count`という実装詳細を
 * 意識させないため（同じ値を`{ days: n, count: n }`のように2つのキーへ書く重複が
 * dry-reviewerレビューで指摘された、2026-10）、`count`の明示指定を優先しつつ、
 * 無ければ「`vars`が唯一持つ数量」を暗黙のcountとして使う。複数の数量を持つキーで
 * 特定の1つを基準にしたい場合のみ`count`を明示する。 */
function resolveCount(vars: Record<string, string | number> | undefined): string | number | undefined {
  if (vars === undefined) {
    return undefined
  }
  if ('count' in vars) {
    return vars.count
  }
  const values = Object.values(vars)
  return values.length === 1 ? values[0] : undefined
}

/**
 * ドット区切りキーでロケール文言を取得する（CODING_RULES.md「ロケールキー」）。
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
    const isSingular = Number(resolveCount(vars)) === 1
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
