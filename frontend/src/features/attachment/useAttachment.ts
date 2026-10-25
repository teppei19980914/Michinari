/** 添付ファイルの通信フック（開発Todo_添付ファイル機能_v1.0）。goal非依存の共通プールのため
 * キャッシュキーはgoalIdを持たない。 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  deleteAttachment,
  getAttachmentLimits,
  listAttachments,
  uploadAttachment,
} from '../../api/attachment'
import { QUERY_KEYS } from '../../constants/queryKeys'

/** 画面が表示・事前チェックに使う上限（タブを開いたときに一度だけ読む）。 */
export function useAttachmentLimits() {
  return useQuery({
    queryKey: QUERY_KEYS.attachmentLimits(),
    queryFn: getAttachmentLimits,
    staleTime: Infinity,
  })
}

/** 登録済み添付ファイルの一覧（A9、目標一覧画面近くの管理画面・各選択UIで共有）。 */
export function useAttachments() {
  return useQuery({
    queryKey: QUERY_KEYS.attachments(),
    queryFn: listAttachments,
  })
}

/** PDFの登録。成功時は一覧のキャッシュを無効化する。 */
export function useUploadAttachment() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (file: File) => uploadAttachment(file),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.attachments() })
    },
  })
}

/** 添付ファイルの削除（常に許可、P3）。成功時は一覧のキャッシュを無効化する。 */
export function useDeleteAttachment() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (attachmentId: number) => deleteAttachment(attachmentId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.attachments() })
    },
  })
}
