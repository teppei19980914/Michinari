import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { t } from '../../locales/t'
import { Card } from '../../components/Card'
import { Button } from '../../components/Button'
import { useToast } from '../../components/Toast'
import { deactivateWorkMember, deleteWorkMember, type WorkMemberRead } from '../../api/goals'
import { QUERY_KEYS } from '../../constants/queryKeys'
import { WorkMemberForm } from './WorkMemberForm'

function WorkMemberRow({
  goalId,
  member,
  readOnly,
}: {
  goalId: number
  member: WorkMemberRead
  readOnly: boolean
}) {
  const queryClient = useQueryClient()
  const { showApiError } = useToast()
  const [editing, setEditing] = useState(false)

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: QUERY_KEYS.goal(goalId) })
    queryClient.invalidateQueries({ queryKey: QUERY_KEYS.activeWorkAssignments() })
  }

  const deactivateMutation = useMutation({
    mutationFn: () => deactivateWorkMember(member.id),
    onSuccess: invalidate,
    onError: showApiError,
  })
  const deleteMutation = useMutation({
    mutationFn: () => deleteWorkMember(member.id),
    onSuccess: invalidate,
    onError: showApiError,
  })

  if (editing) {
    return <WorkMemberForm goalId={goalId} member={member} onDone={() => setEditing(false)} />
  }

  return (
    <li className="flex flex-col gap-1 rounded-md border border-gray-200 p-3 text-sm">
      <div className="flex items-center justify-between">
        <span className="font-medium text-gray-900">
          {member.name}
          {!member.is_active && (
            <span className="ml-2 text-xs text-gray-400">
              {t('goals.workMember.inactiveBadge')}
            </span>
          )}
        </span>
        {member.gender && (
          <span className="text-xs text-gray-500">{t(`goals.workMember.gender.${member.gender}`)}</span>
        )}
      </div>
      {member.characteristics && (
        <p className="whitespace-pre-wrap text-gray-700">{member.characteristics}</p>
      )}
      <p className="text-xs text-gray-400">
        {t('goals.workMember.consentConfirmedAtLabel')}:{' '}
        {member.consent_confirmed_at ?? t('goals.workMember.consentNotConfirmed')}
      </p>
      {!readOnly && (
        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={() => setEditing(true)}>
            {t('common.action.edit')}
          </Button>
          {member.is_active && (
            <Button
              variant="secondary"
              disabled={deactivateMutation.isPending}
              onClick={() => deactivateMutation.mutate()}
            >
              {t('goals.workMember.deactivateButton')}
            </Button>
          )}
          <Button
            variant="secondary"
            disabled={deleteMutation.isPending}
            onClick={() => deleteMutation.mutate()}
          >
            {t('goals.workMember.deleteButton')}
          </Button>
        </div>
      )}
    </li>
  )
}

/** チームメンバー一覧（要件定義書6.11）。目標詳細画面（WorkAssignmentTab）・
 * 日次報告画面（WorkMemberSection）の双方から表示専用の同一データソースとして使う。
 * データはWorkAssignmentRead.membersに埋め込まれているため、このコンポーネント自身は
 * 一覧取得を行わない（呼び出し元がgoal.work_assignment.membersを渡す）。 */
export function WorkMemberList({
  goalId,
  members,
  readOnly,
}: {
  goalId: number
  members: WorkMemberRead[]
  readOnly: boolean
}) {
  const [adding, setAdding] = useState(false)

  return (
    <Card className="flex flex-col gap-3">
      <h3 className="text-sm font-semibold text-gray-900">{t('goals.workMember.title')}</h3>
      {members.length === 0 && !adding && (
        <p className="text-sm text-gray-500">{t('goals.workMember.empty')}</p>
      )}
      {members.length > 0 && (
        <ul className="flex flex-col gap-2">
          {members.map((member) => (
            <WorkMemberRow key={member.id} goalId={goalId} member={member} readOnly={readOnly} />
          ))}
        </ul>
      )}
      {!readOnly &&
        (adding ? (
          <WorkMemberForm goalId={goalId} onDone={() => setAdding(false)} />
        ) : (
          <div className="flex justify-end">
            <Button variant="secondary" onClick={() => setAdding(true)}>
              {t('goals.workMember.addButton')}
            </Button>
          </div>
        ))}
    </Card>
  )
}
