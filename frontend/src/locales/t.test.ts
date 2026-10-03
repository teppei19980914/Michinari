/** ロケール文言の取得処理の分岐を固定する。
 *
 * `src/locales/` は「定数のみで分岐を持たない」としてカバレッジ対象外にしていたが、
 * `t.ts` はキー未解決時のフォールバックと `{{var}}` 置換の分岐を持つ（2026-09-13の
 * カバレッジ監査で判明。Phase 33）。全画面の文言表示がここを通るため対象へ戻して固定する。
 *
 * 置換アルゴリズムの検証には差し替えロケールを使う。実ロケール（`ja.json`）の特定の文言に
 * 依存させると、文言を直書きすることになり（CODING_RULES.md ②ゼロハードコーディング）、
 * 文言を変えるたびにテストが落ちるため。実ロケールを読めていること自体は別途確認する。 */
import { afterEach, describe, expect, it, vi } from 'vitest'
import { t } from './t'

/** 差し替えロケールを読み込ませた `t` を得る。
 *
 * `t.ts` は `ja.json` を静的に取り込むため、モジュールを読み込み直さないと差し替えが効かない。 */
async function loadWithLocale(locale: unknown): Promise<typeof t> {
  vi.resetModules()
  vi.doMock('./ja.json', () => ({ default: locale }))
  const loaded = await import('./t')
  return loaded.t
}

afterEach(() => {
  vi.doUnmock('./ja.json')
  vi.resetModules()
})

describe('t（実ロケール）', () => {
  it('resolves a dot separated key against ja.json', () => {
    // 文言そのものではなく「解決できて空でない文字列が返る」ことだけを見る。
    const resolved = t('errors.default')

    expect(typeof resolved).toBe('string')
    expect(resolved).not.toBe('errors.default')
    expect(resolved.length).toBeGreaterThan(0)
  })

  it('returns the key itself when it is not registered', () => {
    expect(t('errors.__not_registered__')).toBe('errors.__not_registered__')
  })
})

describe('t（差し替えロケール）', () => {
  it('resolves a nested key', async () => {
    const scoped = await loadWithLocale({ a: { b: { c: 'value' } } })

    expect(scoped('a.b.c')).toBe('value')
  })

  it('returns the key when the value is not a string', async () => {
    const scoped = await loadWithLocale({ a: { b: 'value' } })

    // 途中のオブジェクトを指した場合。
    expect(scoped('a')).toBe('a')
  })

  it('returns the key when the path runs past a string', async () => {
    const scoped = await loadWithLocale({ a: 'value' })

    // 文字列の先を辿ろうとした場合（typeof が 'object' にならない側）。
    expect(scoped('a.b')).toBe('a.b')
  })

  it('returns the key instead of throwing when the locale holds a null node', async () => {
    const scoped = await loadWithLocale({ a: null })

    // typeof null === 'object' のため、null を除外しないと添字アクセスで例外になる。
    expect(scoped('a.b')).toBe('a.b')
  })

  it('returns the text unchanged when no variables are given', async () => {
    const scoped = await loadWithLocale({ a: 'すべて{{name}}' })

    expect(scoped('a')).toBe('すべて{{name}}')
  })

  it('replaces every placeholder, including repeats', async () => {
    const scoped = await loadWithLocale({ a: '{{name}}と{{name}}と{{other}}' })

    expect(scoped('a', { name: 'A', other: 'B' })).toBe('AとAとB')
  })

  it('stringifies numeric values', async () => {
    const scoped = await loadWithLocale({ a: '残り{{days}}日' })

    expect(scoped('a', { days: 3 })).toBe('残り3日')
  })

  it('leaves placeholders that have no matching variable', async () => {
    const scoped = await loadWithLocale({ a: '{{given}}と{{missing}}' })

    expect(scoped('a', { given: 'X' })).toBe('Xと{{missing}}')
  })

  it('returns the text unchanged when the variables object is empty', async () => {
    const scoped = await loadWithLocale({ a: '{{name}}' })

    expect(scoped('a', {})).toBe('{{name}}')
  })
})
