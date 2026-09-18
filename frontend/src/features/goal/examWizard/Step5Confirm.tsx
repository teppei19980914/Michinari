import { t } from '../../../locales/t'
import { Card } from '../../../components/Card'
import type { ExamMaterialDraft, ExamSubjectDraft } from './examWizardDrafts'

/** ウィザードStep5（確認して開始。仕様書「資格モードの作成ウィザード」）。
 * 負荷係数・必要連続時間・環境タグ・品質指標の方式はここでは扱わず、目標詳細画面から
 * 後で変更できる旨を案内する。 */
export function Step5Confirm({
  examName,
  subjects,
  materials,
}: {
  examName: string
  subjects: ExamSubjectDraft[]
  materials: ExamMaterialDraft[]
}) {
  return (
    <div className="flex flex-col gap-3">
      <Card className="flex flex-col gap-2">
        <p className="font-medium text-gray-900">{examName}</p>
        <ul className="flex flex-col gap-1 text-sm text-gray-700">
          {subjects.map((subject) => (
            <li key={subject.name}>
              {subject.name} ―{' '}
              {subject.examDateType === 'RANGE'
                ? `${subject.examDateFrom} 〜 ${subject.examDateTo}`
                : subject.examDateFixed}
            </li>
          ))}
        </ul>
        <ul className="flex flex-col gap-1 text-sm text-gray-700">
          {materials.map((material) => (
            <li key={material.name}>
              {material.name}（{material.totalAmount}
              {material.unitLabel} × {material.plannedCycles}
              {t('goals.examWizard.step5.cyclesUnit')}）
            </li>
          ))}
        </ul>
      </Card>
      <p className="text-sm text-gray-600">{t('goals.examWizard.step5.advancedSettingsNotice')}</p>
    </div>
  )
}
