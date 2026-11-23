import { describe, expect, it } from 'vitest'
import { insertBelow, moveByOffset, removeAt } from './scheduleRowOrdering'

describe('moveByOffset', () => {
  it('上へ移動すると前の要素と入れ替わる', () => {
    expect(moveByOffset(['a', 'b', 'c'], 1, -1)).toEqual(['b', 'a', 'c'])
  })

  it('下へ移動すると後の要素と入れ替わる', () => {
    expect(moveByOffset(['a', 'b', 'c'], 1, 1)).toEqual(['a', 'c', 'b'])
  })

  it('先頭より上へは移動できない（変更なし）', () => {
    expect(moveByOffset(['a', 'b', 'c'], 0, -1)).toEqual(['a', 'b', 'c'])
  })

  it('末尾より下へは移動できない（変更なし）', () => {
    expect(moveByOffset(['a', 'b', 'c'], 2, 1)).toEqual(['a', 'b', 'c'])
  })
})

describe('insertBelow', () => {
  it('指定したインデックスの直下に挿入する', () => {
    expect(insertBelow(['a', 'b', 'c'], 0, 'x')).toEqual(['a', 'x', 'b', 'c'])
  })

  it('末尾の行の直下に挿入すると配列の末尾になる', () => {
    expect(insertBelow(['a', 'b', 'c'], 2, 'x')).toEqual(['a', 'b', 'c', 'x'])
  })
})

describe('removeAt', () => {
  it('指定したインデックスの要素だけを取り除く', () => {
    expect(removeAt(['a', 'b', 'c'], 1)).toEqual(['a', 'c'])
  })
})
