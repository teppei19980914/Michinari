/** 全画面の `t('a.b.c')` 呼び出し（リテラルキーのみ）が `ja.json` 上で文字列として解決できることを
 * 横断的に固定する。
 *
 * 個別画面のテストは `t(key)` で期待文言を組み立てて `getByText`/`getByLabelText` と突き合わせる
 * 方式が多いが、`ja.json` 側のキーが誤った階層にあり本文言が解決できない場合、テストと本体
 * コードが同じ誤ったキー文字列（`t()`のキー未解決時フォールバック仕様、`t.ts`参照）で一致して
 * しまい、テストが誤って成功する（トートロジー）。読書のクイック作成モーダルで
 * `goals.new.quickCreate.reading.titleLabel` 等が画面に生のキーのまま表示された不具合
 * （2026-09-26、`ja.json`のquickCreateがgoals.new配下ではなくgoals直下に誤って置かれていた）は
 * この盲点で個別画面のテストをすり抜けた。本テストは`ja.json`を直接読み、個別画面のテストに
 * 依存せずキー解決の可否だけを機械的に検証する。 */
import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join, relative } from 'node:path'
import { describe, expect, it } from 'vitest'
import en from './en.json'
import ja from './ja.json'

const SRC_DIR = join(__dirname, '..')
const LITERAL_KEY_CALL = /\bt\(\s*(['"])([a-zA-Z0-9_.]+)\1/g

/** 対応言語ごとのロケール辞書（`t.ts`の`MESSAGES`と同じ組）。日英で翻訳キーの抜け漏れが
 * 片方だけ起きないよう、両方に対して解決可能性を検証する。 */
const LOCALES: Record<string, unknown> = { ja, en }

function collectSourceFiles(dir: string): string[] {
  const files: string[] = []
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry)
    const stat = statSync(full)
    if (stat.isDirectory()) {
      files.push(...collectSourceFiles(full))
      continue
    }
    if (/\.(ts|tsx)$/.test(entry) && !entry.endsWith('.test.ts') && !entry.endsWith('.test.tsx')) {
      files.push(full)
    }
  }
  return files
}

/** 文字列、または`{ one?, other }`形式の複数形オブジェクトなら解決できたとみなす
 * （`t.ts`の`isPluralValue`と同じ判定基準）。 */
function isResolvable(messages: unknown, key: string): boolean {
  const value = key
    .split('.')
    .reduce<unknown>(
      (node, part) => (typeof node === 'object' && node !== null ? (node as Record<string, unknown>)[part] : undefined),
      messages,
    )
  if (typeof value === 'string') {
    return true
  }
  return (
    typeof value === 'object' &&
    value !== null &&
    typeof (value as Record<string, unknown>).other === 'string'
  )
}

describe('t()のリテラルキー呼び出しが全ロケールで解決できること', () => {
  it.each(Object.entries(LOCALES))('本番コード中の全 t(\'...\') 呼び出しが%sで解決できる', (_locale, messages) => {
    const unresolved: string[] = []
    for (const file of collectSourceFiles(SRC_DIR)) {
      if (relative(SRC_DIR, file).startsWith(join('locales'))) continue
      const content = readFileSync(file, 'utf8')
      for (const match of content.matchAll(LITERAL_KEY_CALL)) {
        const key = match[2]
        if (!isResolvable(messages, key)) {
          unresolved.push(`${relative(SRC_DIR, file)}: ${key}`)
        }
      }
    }
    expect(unresolved).toEqual([])
  })
})
