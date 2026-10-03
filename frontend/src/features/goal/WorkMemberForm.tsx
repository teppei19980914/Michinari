import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { t } from '../../locales/t'
import { Card } from '../../components/Card'
import { Button } from '../../components/Button'
import { useToast } from '../../components/Toast'
import { createWorkMember, updateWorkMember, type WorkMemberRead } from '../../api/goals'
import { QUERY_KEYS } from '../../constants/queryKeys'
import { WorkMemberFormFields, type GenderOption } from './WorkMemberFormFields'

/** チームメンバーの追加・編集フォーム（要件定義書6.11「チームメンバー管理」）。
 *
 * 目標詳細画面（WorkMemberList、WorkAssignmentTabの子）・日次報告画面（WorkMemberSection）
 * の双方から使う共通コンポーネント。同じAPIを叩き同じクエリキーを無効化することで、
 * 追加の同期機構なしに双方の画面へ変更が伝播する（要件定義書6.11「同期」）。
 *
 * 特徴・性格（characteristics）は本アプリ初の第三者PIIフィールドであり、保存の都度
 * 「本人確認済み」チェックを要求する（サーバ側でも強制、work_member_service参照）。
 * 特徴・性格の内容を変更したら、以前のチェック状態を持ち越さずリセットする
 * （古い内容への同意を新しい内容の同意として黙って使い回さないため、
 * WorkMemberFormFields側で実施）。
 */
export function WorkMemberForm({
  goalId,
  member,
  onDone,
}: {
  goalId: number
  member?: WorkMemberRead
  onDone: () => void
}) {
  const queryClient = useQueryClient()
  const { showApiError } = useToast()
  const [name, setName] = useState(member?.name ?? '')
  const [gender, setGender] = useState<GenderOption | ''>(
    (member?.gender as GenderOption | null) ?? '',
  )
  const [characteristics, setCharacteristics] = useState(member?.characteristics ?? '')
  const [consentConfirmed, setConsentConfirmed] = useState(false)

  const payload = {
    name,
    gender: gender === '' ? null : gender,
    characteristics: characteristics === '' ? null : characteristics,
    consent_confirmed: consentConfirmed,
  }

  const mutation = useMutation({
    mutationFn: () =>
      member ? updateWorkMember(member.id, payload) : createWorkMember(goalId, payload),
    meta: { overlay: 'saving' },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.goal(goalId) })
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.activeWorkAssignments() })
      onDone()
    },
    onError: showApiError,
  })

  return (
    <Card>
      <form
        className="flex flex-col gap-3"
        onSubmit={(event) => {
          event.preventDefault()
          mutation.mutate()
        }}
      >
        <WorkMemberFormFields
          name={name}
          onChangeName={setName}
          gender={gender}
          onChangeGender={setGender}
          characteristics={characteristics}
          onChangeCharacteristics={setCharacteristics}
          consentConfirmed={consentConfirmed}
          onChangeConsentConfirmed={setConsentConfirmed}
        />
        <div className="flex justify-end gap-2">
          <Button type="button" variant="secondary" onClick={onDone}>
            {t('common.action.cancel')}
          </Button>
          <Button type="submit" disabled={mutation.isPending}>
            {t('common.action.save')}
          </Button>
        </div>
      </form>
    </Card>
  )
}
