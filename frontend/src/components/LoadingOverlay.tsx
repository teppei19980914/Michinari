import { useMutationState } from '@tanstack/react-query'
import { CHARACTER_ICONS, OVERLAY_ICON, type OverlayKind } from '../constants/characterIcons'
import { t } from '../locales/t'

/** 複数種別が同時に進行中の場合の優先順位（削除は取り消せないため保存より優先して伝える）。 */
const OVERLAY_PRIORITY: readonly OverlayKind[] = ['deleting', 'saving']

const OVERLAY_LOCALE_KEY: Record<OverlayKind, string> = {
  saving: 'common.overlay.saving',
  deleting: 'common.overlay.deleting',
}

/** 進行中のミューテーションから、表示すべきオーバーレイ種別を横断的に判定する。 */
function useActiveOverlayKind(): OverlayKind | null {
  const pendingKinds = useMutationState<OverlayKind | undefined>({
    filters: {
      status: 'pending',
      predicate: (mutation) => mutation.options.meta?.overlay != null,
    },
    select: (mutation) => mutation.options.meta?.overlay,
  })

  return OVERLAY_PRIORITY.find((kind) => pendingKinds.includes(kind)) ?? null
}

/**
 * 保存中・生成AI疎通中・削除中に画面全体をブロックする共通オーバーレイ（仕様書v1.1 13章）。
 *
 * 各画面のuseMutationに`meta: { overlay: 'saving' | 'deleting' }`を付けるだけで自動的に
 * 表示される。TanStack Queryのミューテーションキャッシュをapp全体で横断的に監視するため、
 * 呼び出し元が表示・非表示を個別に制御する必要がなく、meta付け漏れ以外での横展開漏れが
 * 起きない（App.tsxのLayoutに1箇所だけマウントする）。
 *
 * 生成AI疎通中は専用アイコンを設けず、UI-05（登録中）と同じ`saving`種別を流用する
 * （仕様書v1.1 13.3、振り返り入力・進捗入力と同様に記録行為の一種とみなす）。
 */
export function LoadingOverlay() {
  const kind = useActiveOverlayKind()
  if (!kind) {
    return null
  }

  return (
    <div
      role="alert"
      aria-live="assertive"
      className="fixed inset-0 z-[60] flex flex-col items-center justify-center gap-4 bg-black/40"
    >
      <img src={CHARACTER_ICONS[OVERLAY_ICON[kind]]} alt="" className="h-32 w-32" />
      <p className="rounded-md bg-white px-4 py-2 text-sm font-medium text-gray-900 shadow-lg">
        {t(OVERLAY_LOCALE_KEY[kind])}
      </p>
    </div>
  )
}
