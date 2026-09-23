/** チームメンバーフォームの入力欄（WorkMemberForm.tsxから切り出し。
 * ExamResultFields.tsxと同じ理由＝1関数100行の上限、CODING_RULES.md「保守性（複雑度）」）。
 * 入力値の保持・送信内容の組み立ては呼び出し元（WorkMemberForm）に残す。 */
import { t } from '../../locales/t'
import { Input } from '../../components/Input'
import { Textarea } from '../../components/Textarea'

export const GENDER_OPTIONS = ['MALE', 'FEMALE', 'OTHER'] as const
export type GenderOption = (typeof GENDER_OPTIONS)[number]

export function WorkMemberFormFields({
  name,
  onChangeName,
  gender,
  onChangeGender,
  characteristics,
  onChangeCharacteristics,
  consentConfirmed,
  onChangeConsentConfirmed,
}: {
  name: string
  onChangeName: (value: string) => void
  gender: GenderOption | ''
  onChangeGender: (value: GenderOption | '') => void
  characteristics: string
  onChangeCharacteristics: (value: string) => void
  consentConfirmed: boolean
  onChangeConsentConfirmed: (value: boolean) => void
}) {
  return (
    <>
      <label className="flex flex-col gap-1 text-sm text-gray-700">
        {t('goals.workMember.nameLabel')}
        <Input value={name} onChange={(e) => onChangeName(e.target.value)} required />
      </label>
      <label className="flex flex-col gap-1 text-sm text-gray-700">
        {t('goals.workMember.genderLabel')}
        <select
          className="rounded-md border border-gray-300 px-3 py-2 text-sm"
          value={gender}
          onChange={(e) => onChangeGender(e.target.value as GenderOption | '')}
        >
          <option value="">{t('goals.workMember.gender.NONE')}</option>
          {GENDER_OPTIONS.map((value) => (
            <option key={value} value={value}>
              {t(`goals.workMember.gender.${value}`)}
            </option>
          ))}
        </select>
      </label>
      <label className="flex flex-col gap-1 text-sm text-gray-700">
        {t('goals.workMember.characteristicsLabel')}
        <Textarea
          value={characteristics}
          onChange={(e) => {
            onChangeCharacteristics(e.target.value)
            onChangeConsentConfirmed(false)
          }}
          rows={3}
          placeholder={t('goals.workMember.characteristicsPlaceholder')}
        />
      </label>
      {characteristics !== '' && (
        <label className="flex items-start gap-2 text-sm text-gray-700">
          <input
            type="checkbox"
            className="mt-1"
            checked={consentConfirmed}
            onChange={(e) => onChangeConsentConfirmed(e.target.checked)}
          />
          <span>
            {t('goals.workMember.consentCheckbox')}
            <span className="mt-0.5 block text-xs text-gray-500">
              {t('goals.workMember.consentHint')}
            </span>
          </span>
        </label>
      )}
    </>
  )
}
