/**
 * index.cssのカスケード順序を検査する（UIリッチ化）。
 *
 * CSSは同じ詳細度のセレクタが同じプロパティを競合させた場合、後に書かれたルールが勝つ。
 * [data-theme='dark']と[data-accent='...']はどちらも属性セレクタ1つ分の詳細度で並び、
 * <html>には両方の属性が同時に付くため、書く順序を誤ると「アクセント色をblue以外にした
 * 状態でダークモードにすると、ダーク側の調整値がアクセント色側のライト用固定値で
 * 上書きされる」不具合が起きる（2026-10利用者検証で実際に発生）。
 *
 * 手動確認だけでは同種の不具合の再発に気づけないため、index.cssを解析して
 * [data-theme='dark']ブロックが、同じプロパティを持つ他の属性セレクタブロックより
 * 必ず後ろに書かれていることを機械的に固定する。
 */
import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

type Block = { selector: string; start: number; properties: string[] }

function parseBlocks(css: string): Block[] {
  const blocks: Block[] = []
  const blockPattern = /([^{}/]+)\{([^{}]*)\}/g
  let match: RegExpExecArray | null
  while ((match = blockPattern.exec(css)) !== null) {
    const selector = match[1].trim()
    const body = match[2]
    const properties = [...body.matchAll(/(--[a-zA-Z0-9-]+)\s*:/g)].map((m) => m[1])
    if (properties.length > 0) {
      blocks.push({ selector, start: match.index, properties })
    }
  }
  return blocks
}

describe('index.cssのカスケード順序（[data-theme=dark] vs [data-accent=...]）', () => {
  const css = readFileSync(join(dirname(fileURLToPath(import.meta.url)), 'index.css'), 'utf-8')
  const blocks = parseBlocks(css)
  const darkBlocks = blocks.filter((b) => b.selector.includes("[data-theme='dark']"))
  const accentBlocks = blocks.filter((b) => /\[data-accent='[a-z]+'\]/.test(b.selector))

  it('index.cssに[data-theme=dark]ブロックと[data-accent=...]ブロックの両方が存在する', () => {
    // この前提が崩れたら本テスト自体が無意味になるため、前提確認を分けて固定する。
    expect(darkBlocks.length).toBeGreaterThan(0)
    expect(accentBlocks.length).toBeGreaterThanOrEqual(3)
  })

  it.each(darkBlocks.map((darkBlock, i) => [i, darkBlock] as const))(
    '[data-theme=dark]ブロック#%iは、同じプロパティを持つ[data-accent=...]ブロックより後ろにある',
    (_, darkBlock) => {
      for (const accentBlock of accentBlocks) {
        const shared = darkBlock.properties.filter((p) => accentBlock.properties.includes(p))
        for (const prop of shared) {
          expect(
            darkBlock.start,
            `${prop} は ${accentBlock.selector} にも定義されているため、` +
              `[data-theme='dark'] はそれより後ろに書く必要がある`,
          ).toBeGreaterThan(accentBlock.start)
        }
      }
    },
  )
})
