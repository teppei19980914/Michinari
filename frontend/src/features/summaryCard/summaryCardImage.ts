/** ふりかえりまとめ・共有カードのSVG→PNG変換・クリップボードコピー（ロジック・プロンプト編
 * 28.2「画像化（フロント）」）。新規ライブラリは追加せず、ブラウザ標準APIのみで実現する
 * （開発Todo「まとめと共有カード」v1.0 D6）。 */

function loadImage(url: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const image = new Image()
    image.onload = () => resolve(image)
    image.onerror = () => reject(new Error('Failed to load the card as an image'))
    image.src = url
  })
}

function canvasToPngBlob(canvas: HTMLCanvasElement): Promise<Blob> {
  return new Promise((resolve, reject) => {
    canvas.toBlob((blob) => {
      if (blob) {
        resolve(blob)
      } else {
        reject(new Error('Failed to encode the card as PNG'))
      }
    }, 'image/png')
  })
}

/** カードのSVG要素をPNG画像のBlobへ変換する。SVGの`width`/`height`属性（SummaryCardPreview
 * が明示的に付与、CSS依存ではない）をそのままcanvasの画素寸法に使う。 */
export async function svgElementToPngBlob(svg: SVGSVGElement): Promise<Blob> {
  // Webフォントの読み込み待ち。未読込のまま描画すると、ラスタライズの瞬間だけ文字が
  // 欠けた・代替フォントの状態で固定されてしまう（28.2）。
  await document.fonts.ready

  const serialized = new XMLSerializer().serializeToString(svg)
  const svgBlob = new Blob([serialized], { type: 'image/svg+xml;charset=utf-8' })
  const url = URL.createObjectURL(svgBlob)
  try {
    const image = await loadImage(url)
    const width = Number(svg.getAttribute('width'))
    const height = Number(svg.getAttribute('height'))
    const canvas = document.createElement('canvas')
    canvas.width = width
    canvas.height = height
    const context = canvas.getContext('2d')
    if (!context) {
      throw new Error('2D canvas context is not available')
    }
    context.drawImage(image, 0, 0, width, height)
    return await canvasToPngBlob(canvas)
  } finally {
    URL.revokeObjectURL(url)
  }
}

/** 実行環境がクリップボードへの画像コピーに対応しているか（Clipboard API + ClipboardItem）。
 * ボタンの有効/無効を画面側で判断するために公開する。 */
export function isClipboardImageCopySupported(): boolean {
  return typeof navigator.clipboard?.write === 'function' && typeof ClipboardItem !== 'undefined'
}

/** PNG画像のBlobをクリップボードへコピーする。非対応環境では例外を投げる（呼び出し側は
 * `isClipboardImageCopySupported`で事前にボタンを無効化する想定）。 */
export async function copyPngBlobToClipboard(blob: Blob): Promise<void> {
  if (!isClipboardImageCopySupported()) {
    throw new Error('Clipboard image copy is not supported in this environment')
  }
  await navigator.clipboard.write([new ClipboardItem({ [blob.type]: blob })])
}
