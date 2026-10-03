/** AI評価レポート生成カード（WorkEvaluationReportTab.tsxから切り出し。
 * ExamResultFields.tsxと同じ理由＝1関数100行の上限、CODING_RULES.md「保守性（複雑度）」）。 */
import { t } from '../../locales/t'
import { Card } from '../../components/Card'
import { Textarea } from '../../components/Textarea'
import { Button } from '../../components/Button'
import { AiUnconfiguredNotice } from '../../components/AiUnconfiguredNotice'
import type { WorkMemberRead } from '../../api/goals'

export function WorkEvaluationGenerateCard({
  activeMembers,
  memberId,
  onChangeMemberId,
  considerations,
  onChangeConsiderations,
  aiConfigured,
  isPending,
  onGenerate,
}: {
  activeMembers: WorkMemberRead[]
  memberId: number | ''
  onChangeMemberId: (value: number | '') => void
  considerations: string
  onChangeConsiderations: (value: string) => void
  aiConfigured: boolean
  isPending: boolean
  onGenerate: () => void
}) {
  return (
    <Card className="flex flex-col gap-3">
      <label className="flex flex-col gap-1 text-sm text-gray-700">
        {t('goals.workEvaluationReport.memberSelectLabel')}
        <select
          className="rounded-md border border-gray-300 px-3 py-2 text-sm"
          value={memberId}
          onChange={(e) => onChangeMemberId(e.target.value === '' ? '' : Number(e.target.value))}
        >
          <option value="">{t('goals.workEvaluationReport.memberSelectPlaceholder')}</option>
          {activeMembers.map((member) => (
            <option key={member.id} value={member.id}>
              {member.name}
            </option>
          ))}
        </select>
      </label>
      <label className="flex flex-col gap-1 text-sm text-gray-700">
        {t('goals.workEvaluationReport.considerationsLabel')}
        <Textarea
          value={considerations}
          onChange={(e) => onChangeConsiderations(e.target.value)}
          rows={3}
          placeholder={t('goals.workEvaluationReport.considerationsPlaceholder')}
        />
      </label>
      {aiConfigured ? (
        <div className="flex justify-end">
          <Button disabled={memberId === '' || considerations === '' || isPending} onClick={onGenerate}>
            {t('goals.workEvaluationReport.generateButton')}
          </Button>
        </div>
      ) : (
        <AiUnconfiguredNotice />
      )}
    </Card>
  )
}
