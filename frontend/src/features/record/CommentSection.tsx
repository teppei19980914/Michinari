import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { t } from '../../locales/t'
import { Card } from '../../components/Card'
import { Button } from '../../components/Button'
import { Textarea } from '../../components/Textarea'
import { useToast } from '../../components/Toast'
import { createComment, deleteComment, updateComment } from '../../api/records'
import type { components } from '../../types/api.d.ts'

type CommentRead = components['schemas']['CommentRead']

function CommentItem({ targetDate, comment }: { targetDate: string; comment: CommentRead }) {
  const queryClient = useQueryClient()
  const { showApiError } = useToast()
  const [editing, setEditing] = useState(false)
  const [body, setBody] = useState(comment.body)

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ['record', targetDate] })

  const updateMutation = useMutation({
    mutationFn: () => updateComment(comment.id, body),
    onSuccess: () => {
      invalidate()
      setEditing(false)
    },
    onError: showApiError,
  })
  const deleteMutation = useMutation({
    mutationFn: () => deleteComment(comment.id),
    onSuccess: invalidate,
    onError: showApiError,
  })

  if (editing) {
    return (
      <Card className="flex flex-col gap-2">
        <Textarea rows={2} value={body} onChange={(e) => setBody(e.target.value)} />
        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={() => setEditing(false)}>
            {t('common.action.cancel')}
          </Button>
          <Button disabled={updateMutation.isPending} onClick={() => updateMutation.mutate()}>
            {t('common.action.save')}
          </Button>
        </div>
      </Card>
    )
  }

  return (
    <Card className="flex items-start justify-between gap-2">
      <div>
        <p className="text-sm text-gray-900 whitespace-pre-wrap">{comment.body}</p>
        <p className="mt-1 text-xs text-gray-400">
          {new Date(comment.created_at).toLocaleString('ja-JP')}
        </p>
      </div>
      <div className="flex shrink-0 gap-2">
        <Button variant="secondary" onClick={() => setEditing(true)}>
          {t('common.action.edit')}
        </Button>
        <Button
          variant="secondary"
          onClick={() => {
            if (window.confirm(t('common.confirmDelete'))) {
              deleteMutation.mutate()
            }
          }}
        >
          {t('common.action.delete')}
        </Button>
      </div>
    </Card>
  )
}

/** コメント欄（SC-08「コメントの追加、修正、削除が可能」、仕様書6.7）。 */
export function CommentSection({
  targetDate,
  comments,
}: {
  targetDate: string
  comments: CommentRead[]
}) {
  const queryClient = useQueryClient()
  const { showApiError } = useToast()
  const [newBody, setNewBody] = useState('')

  const createMutation = useMutation({
    mutationFn: () => createComment(targetDate, newBody),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['record', targetDate] })
      setNewBody('')
    },
    onError: showApiError,
  })

  return (
    <div className="flex flex-col gap-2">
      <h2 className="font-medium text-gray-900">{t('dailyReportView.comments.title')}</h2>
      {comments.length === 0 && (
        <p className="text-sm text-gray-500">{t('dailyReportView.comments.empty')}</p>
      )}
      {comments.map((comment) => (
        <CommentItem key={comment.id} targetDate={targetDate} comment={comment} />
      ))}
      <div className="flex gap-2">
        <Textarea
          rows={2}
          className="flex-1"
          value={newBody}
          onChange={(e) => setNewBody(e.target.value)}
          placeholder={t('dailyReportView.comments.newPlaceholder')}
        />
        <Button
          disabled={createMutation.isPending || newBody.trim() === ''}
          onClick={() => createMutation.mutate()}
        >
          {t('dailyReportView.comments.addButton')}
        </Button>
      </div>
    </div>
  )
}
