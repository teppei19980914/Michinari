import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import {
  copyPngBlobToClipboard,
  isClipboardImageCopySupported,
  svgElementToPngBlob,
} from './summaryCardImage'

/** jsdomは`document.fonts`（FontFaceSet）・`Image`のデコード・`HTMLCanvasElement`の
 * 2D描画・`navigator.clipboard`の画像書き込みのいずれも実装していないため、ブラウザの
 * 挙動を模した最小限のスタブに差し替える（CODING_RULES.mdテストカバレッジ、既存の
 * downloadBlob.ts等と同じ「DOM API依存のユーティリティ」としての扱い）。 */

type FakeImageMode = 'success' | 'error'

function installFakeImage(mode: FakeImageMode): void {
  class FakeImage {
    onload: (() => void) | null = null
    onerror: (() => void) | null = null
    naturalWidth = 600
    naturalHeight = 400
    set src(_value: string) {
      queueMicrotask(() => {
        if (mode === 'success') {
          this.onload?.()
        } else {
          this.onerror?.()
        }
      })
    }
  }
  vi.stubGlobal('Image', FakeImage)
}

function installFontsReady(): void {
  Object.defineProperty(document, 'fonts', {
    value: { ready: Promise.resolve() },
    configurable: true,
  })
}

function makeSvg(): SVGSVGElement {
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg')
  svg.setAttribute('width', '600')
  svg.setAttribute('height', '400')
  return svg
}

beforeEach(() => {
  installFontsReady()
  vi.stubGlobal('URL', {
    ...URL,
    createObjectURL: vi.fn(() => 'blob:fake-url'),
    revokeObjectURL: vi.fn(),
  })
})

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('svgElementToPngBlob', () => {
  it('SVGをcanvasへ描画し、PNGのBlobを返す', async () => {
    installFakeImage('success')
    const drawImage = vi.fn()
    vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue({
      drawImage,
    } as unknown as CanvasRenderingContext2D)
    vi.spyOn(HTMLCanvasElement.prototype, 'toBlob').mockImplementation((callback) => {
      callback(new Blob(['png'], { type: 'image/png' }))
    })

    const blob = await svgElementToPngBlob(makeSvg())

    expect(blob.type).toBe('image/png')
    expect(drawImage).toHaveBeenCalledWith(expect.anything(), 0, 0, 600, 400)
  })

  it('2D contextが取得できない場合はエラーになる', async () => {
    installFakeImage('success')
    vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue(null)

    await expect(svgElementToPngBlob(makeSvg())).rejects.toThrow(
      '2D canvas context is not available',
    )
  })

  it('画像としての読み込みに失敗した場合はエラーになる', async () => {
    installFakeImage('error')

    await expect(svgElementToPngBlob(makeSvg())).rejects.toThrow(
      'Failed to load the card as an image',
    )
  })

  it('PNGへの変換に失敗した場合はエラーになる', async () => {
    installFakeImage('success')
    vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue({
      drawImage: vi.fn(),
    } as unknown as CanvasRenderingContext2D)
    vi.spyOn(HTMLCanvasElement.prototype, 'toBlob').mockImplementation((callback) => {
      callback(null)
    })

    await expect(svgElementToPngBlob(makeSvg())).rejects.toThrow(
      'Failed to encode the card as PNG',
    )
  })
})

describe('isClipboardImageCopySupported / copyPngBlobToClipboard', () => {
  it('対応環境ではtrueを返し、ClipboardItemでコピーする', async () => {
    const write = vi.fn().mockResolvedValue(undefined)
    vi.stubGlobal(
      'ClipboardItem',
      class {
        items: Record<string, Blob>
        constructor(items: Record<string, Blob>) {
          this.items = items
        }
      },
    )
    vi.stubGlobal('navigator', { ...navigator, clipboard: { write } })

    expect(isClipboardImageCopySupported()).toBe(true)
    const blob = new Blob(['png'], { type: 'image/png' })
    await copyPngBlobToClipboard(blob)
    expect(write).toHaveBeenCalledTimes(1)
  })

  it('非対応環境ではfalseを返し、コピーはエラーになる', async () => {
    vi.stubGlobal('ClipboardItem', undefined)
    vi.stubGlobal('navigator', { ...navigator, clipboard: undefined })

    expect(isClipboardImageCopySupported()).toBe(false)
    await expect(copyPngBlobToClipboard(new Blob())).rejects.toThrow(
      'Clipboard image copy is not supported in this environment',
    )
  })

  it('navigator.clipboard.writeはあるがClipboardItemが無い環境でもfalseを返す（古いブラウザの組み合わせ）', () => {
    vi.stubGlobal('ClipboardItem', undefined)
    vi.stubGlobal('navigator', { ...navigator, clipboard: { write: vi.fn() } })

    expect(isClipboardImageCopySupported()).toBe(false)
  })
})
