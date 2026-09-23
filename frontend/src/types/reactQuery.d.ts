import type { OverlayKind } from '../constants/characterIcons'

/**
 * useMutationのmetaにオーバーレイ種別を持たせるための型拡張。
 * LoadingOverlay（frontend/src/components/LoadingOverlay.tsx）がuseMutationStateで
 * meta.overlayを横断的に読み取り、保存中・削除中のブロッキング表示を出し分ける。
 */
declare module '@tanstack/react-query' {
  interface Register {
    mutationMeta: {
      overlay?: OverlayKind
    }
  }
}
