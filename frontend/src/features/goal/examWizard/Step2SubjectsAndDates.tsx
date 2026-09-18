import { t } from '../../../locales/t'
import { Card } from '../../../components/Card'
import { Input } from '../../../components/Input'
import { Button } from '../../../components/Button'
import { SubjectExamDateFields } from '../SubjectFormFields'
import { emptySubjectDraft, type ExamSubjectDraft } from './examWizardDrafts'

function SubjectDraftRow({
  draft,
  onChange,
  onRemove,
}: {
  draft: ExamSubjectDraft
  onChange: (next: ExamSubjectDraft) => void
  onRemove: () => void
}) {
  return (
    <Card className="flex flex-col gap-3">
      <div className="flex items-start justify-between gap-2">
        <label className="flex flex-1 flex-col gap-1 text-sm text-gray-700">
          {t('goals.subjects.nameLabel')}
          <Input
            value={draft.name}
            onChange={(e) => onChange({ ...draft, name: e.target.value })}
            required
          />
        </label>
        <Button type="button" variant="secondary" onClick={onRemove}>
          {t('common.action.delete')}
        </Button>
      </div>
      <label className="flex flex-col gap-1 text-sm text-gray-700">
        {t('goals.subjects.passingScoreLabel')}
        <Input
          type="number"
          min={0}
          max={100}
          value={draft.passingScore}
          onChange={(e) => onChange({ ...draft, passingScore: e.target.value })}
        />
      </label>
      <SubjectExamDateFields
        examDateType={draft.examDateType}
        onChangeExamDateType={(value) => onChange({ ...draft, examDateType: value })}
        examDateFrom={draft.examDateFrom}
        onChangeExamDateFrom={(value) => onChange({ ...draft, examDateFrom: value })}
        examDateTo={draft.examDateTo}
        onChangeExamDateTo={(value) => onChange({ ...draft, examDateTo: value })}
        examDateFixed={draft.examDateFixed}
        onChangeExamDateFixed={(value) => onChange({ ...draft, examDateFixed: value })}
      />
    </Card>
  )
}

/** ウィザードStep2（受験日を入れる。仕様書「資格モードの作成ウィザード」）。
 * テンプレート選択時は科目が既に入っているため受験日の入力のみで済み、「その他」選択時は
 * ここで科目自体を追加する（試験名以外の科目情報を入力する画面が他に無いため）。 */
export function Step2SubjectsAndDates({
  subjects,
  onChangeSubjects,
}: {
  subjects: ExamSubjectDraft[]
  onChangeSubjects: (next: ExamSubjectDraft[]) => void
}) {
  return (
    <div className="flex flex-col gap-3">
      <p className="text-sm text-gray-600">{t('goals.examWizard.step2.description')}</p>

      {subjects.map((draft, index) => (
        // eslint-disable-next-line react/no-array-index-key -- 科目名は編集途中で重複しうるため
        <SubjectDraftRow
          key={index}
          draft={draft}
          onChange={(next) =>
            onChangeSubjects(subjects.map((item, itemIndex) => (itemIndex === index ? next : item)))
          }
          onRemove={() => onChangeSubjects(subjects.filter((_, itemIndex) => itemIndex !== index))}
        />
      ))}

      <Button
        type="button"
        variant="secondary"
        onClick={() => onChangeSubjects([...subjects, emptySubjectDraft()])}
      >
        {t('goals.examWizard.step2.addSubject')}
      </Button>
    </div>
  )
}
