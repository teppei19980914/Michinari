import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { t } from '../../locales/t'
import { Card } from '../../components/Card'
import { Input } from '../../components/Input'
import { Button } from '../../components/Button'
import { useToast } from '../../components/Toast'
import {
  createLoadProfile,
  deleteLoadProfile,
  updateLoadProfile,
  type GoalDetailRead,
  type LoadProfileRead,
} from '../../api/goals'

function LoadProfileForm({
  goalId,
  profile,
  onDone,
}: {
  goalId: number
  profile?: LoadProfileRead
  onDone: () => void
}) {
  const queryClient = useQueryClient()
  const { showApiError } = useToast()
  const [dateFrom, setDateFrom] = useState(profile?.date_from ?? '')
  const [dateTo, setDateTo] = useState(profile?.date_to ?? '')
  const [coefficient, setCoefficient] = useState(String(profile?.coefficient ?? '1.0'))
  const [note, setNote] = useState(profile?.note ?? '')

  const payload = {
    date_from: dateFrom,
    date_to: dateTo,
    coefficient: Number(coefficient),
    note: note || null,
  }

  const mutation = useMutation({
    mutationFn: () =>
      profile ? updateLoadProfile(profile.id, payload) : createLoadProfile(goalId, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['goal', goalId] })
      onDone()
    },
    onError: showApiError,
  })

  return (
    <form
      className="flex flex-col gap-3"
      onSubmit={(event) => {
        event.preventDefault()
        mutation.mutate()
      }}
    >
      <div className="flex gap-2">
        <label className="flex flex-1 flex-col gap-1 text-sm text-gray-700">
          {t('goals.loadProfile.dateFromLabel')}
          <Input
            type="date"
            value={dateFrom}
            onChange={(e) => setDateFrom(e.target.value)}
            required
          />
        </label>
        <label className="flex flex-1 flex-col gap-1 text-sm text-gray-700">
          {t('goals.loadProfile.dateToLabel')}
          <Input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} required />
        </label>
        <label className="flex flex-1 flex-col gap-1 text-sm text-gray-700">
          {t('goals.loadProfile.coefficientLabel')}
          <Input
            type="number"
            step="0.1"
            min={0.1}
            value={coefficient}
            onChange={(e) => setCoefficient(e.target.value)}
            required
          />
        </label>
      </div>
      <label className="flex flex-col gap-1 text-sm text-gray-700">
        {t('goals.loadProfile.noteLabel')}
        <Input value={note} onChange={(e) => setNote(e.target.value)} />
      </label>
      <div className="flex justify-end gap-2">
        <Button type="button" variant="secondary" onClick={onDone}>
          {t('common.action.cancel')}
        </Button>
        <Button type="submit" disabled={mutation.isPending}>
          {t('common.action.save')}
        </Button>
      </div>
    </form>
  )
}

/** 負荷プロファイルタブ（仕様書6.2「期間ごとの負荷係数の設定」）。 */
export function LoadProfileTab({
  goal,
  readOnly,
}: {
  goal: GoalDetailRead
  readOnly: boolean
}) {
  const queryClient = useQueryClient()
  const { showApiError } = useToast()
  const [addOpen, setAddOpen] = useState(false)
  const [editingId, setEditingId] = useState<number | null>(null)

  const deleteMutation = useMutation({
    mutationFn: (profileId: number) => deleteLoadProfile(profileId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['goal', goal.id] }),
    onError: showApiError,
  })

  return (
    <div className="flex flex-col gap-3">
      {goal.load_profiles.length === 0 && !addOpen && (
        <p className="text-sm text-gray-500">{t('goals.loadProfile.empty')}</p>
      )}

      {goal.load_profiles.map((profile) =>
        editingId === profile.id ? (
          <Card key={profile.id}>
            <LoadProfileForm goalId={goal.id} profile={profile} onDone={() => setEditingId(null)} />
          </Card>
        ) : (
          <Card key={profile.id} className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-900">
                {profile.date_from} 〜 {profile.date_to}
              </p>
              <p className="text-sm text-gray-500">
                {t('goals.loadProfile.coefficientLabel')}: {profile.coefficient}
                {profile.note ? ` (${profile.note})` : ''}
              </p>
            </div>
            {!readOnly && (
              <div className="flex gap-2">
                <Button variant="secondary" onClick={() => setEditingId(profile.id)}>
                  {t('common.action.edit')}
                </Button>
                <Button
                  variant="secondary"
                  onClick={() => {
                    if (window.confirm(t('common.confirmDelete'))) {
                      deleteMutation.mutate(profile.id)
                    }
                  }}
                >
                  {t('common.action.delete')}
                </Button>
              </div>
            )}
          </Card>
        ),
      )}

      {!readOnly &&
        (addOpen ? (
          <Card>
            <LoadProfileForm goalId={goal.id} onDone={() => setAddOpen(false)} />
          </Card>
        ) : (
          <Button variant="secondary" onClick={() => setAddOpen(true)}>
            {t('goals.loadProfile.addTitle')}
          </Button>
        ))}
    </div>
  )
}
