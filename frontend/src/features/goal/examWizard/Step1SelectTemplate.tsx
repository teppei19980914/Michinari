import { t } from '../../../locales/t'
import { Card } from '../../../components/Card'
import { Input } from '../../../components/Input'
import type { ExamTemplateRead } from '../../../api/examTemplates'

/** ウィザードStep1（試験を選ぶ。仕様書「資格モードの作成ウィザード」）。
 * `selection`は選択中のテンプレートID、または手入力を表す`'OTHER'`、未選択なら`null`。 */
export function Step1SelectTemplate({
  templates,
  isLoading,
  selection,
  examName,
  onSelectTemplate,
  onSelectOther,
  onChangeExamName,
}: {
  templates: ExamTemplateRead[]
  isLoading: boolean
  selection: string | 'OTHER' | null
  examName: string
  onSelectTemplate: (template: ExamTemplateRead) => void
  onSelectOther: () => void
  onChangeExamName: (value: string) => void
}) {
  if (isLoading) {
    return <p className="text-sm text-text-faint">{t('common.loading')}</p>
  }

  return (
    <div className="flex flex-col gap-3">
      <p className="text-sm text-text-muted">{t('goals.examWizard.step1.description')}</p>
      <p className="text-xs text-warning-text-subtle">{t('goals.examWizard.step1.dataDisclaimer')}</p>

      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
        {templates.map((template) => (
          <button
            key={template.id}
            type="button"
            className="text-left"
            onClick={() => onSelectTemplate(template)}
          >
            <Card
              className={
                selection === template.id
                  ? 'border-accent ring-1 ring-accent'
                  : 'hover:border-accent-disabled'
              }
            >
              <span className="font-medium text-text-primary">{template.exam_name}</span>
            </Card>
          </button>
        ))}

        <button type="button" className="text-left" onClick={onSelectOther}>
          <Card className={selection === 'OTHER' ? 'border-accent ring-1 ring-accent' : 'hover:border-accent-disabled'}>
            <span className="font-medium text-text-primary">{t('goals.examWizard.step1.otherOption')}</span>
          </Card>
        </button>
      </div>

      {selection === 'OTHER' && (
        <label className="flex flex-col gap-1 text-sm text-text-secondary">
          {t('goals.examWizard.step1.examNameLabel')}
          <Input value={examName} onChange={(e) => onChangeExamName(e.target.value)} required />
        </label>
      )}
    </div>
  )
}
