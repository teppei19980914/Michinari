import { t } from '../../../locales/t'
import { Card } from '../../../components/Card'
import { Input } from '../../../components/Input'
import { Button } from '../../../components/Button'
import { emptyMaterialDraft, type ExamMaterialDraft, type ExamSubjectDraft } from './examWizardDrafts'

function MaterialDraftRow({
  draft,
  subjects,
  onChange,
  onRemove,
}: {
  draft: ExamMaterialDraft
  subjects: ExamSubjectDraft[]
  onChange: (next: ExamMaterialDraft) => void
  onRemove: () => void
}) {
  function toggleSubject(name: string) {
    const next = draft.subjectNames.includes(name)
      ? draft.subjectNames.filter((item) => item !== name)
      : [...draft.subjectNames, name]
    onChange({ ...draft, subjectNames: next })
  }

  return (
    <Card className="flex flex-col gap-3">
      <div className="flex items-start justify-between gap-2">
        <label className="flex flex-1 flex-col gap-1 text-sm text-gray-700">
          {t('goals.materials.nameLabel')}
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
      <div className="flex gap-2">
        <label className="flex flex-1 flex-col gap-1 text-sm text-gray-700">
          {t('goals.materials.unitLabel')}
          <Input value={draft.unitLabel} onChange={(e) => onChange({ ...draft, unitLabel: e.target.value })} required />
        </label>
        <label className="flex flex-1 flex-col gap-1 text-sm text-gray-700">
          {t('goals.materials.totalAmountLabel')}
          <Input
            type="number"
            min={0}
            value={draft.totalAmount}
            onChange={(e) => onChange({ ...draft, totalAmount: e.target.value })}
            required
          />
        </label>
        <label className="flex flex-1 flex-col gap-1 text-sm text-gray-700">
          {t('goals.materials.plannedCyclesLabel')}
          <Input
            type="number"
            min={1}
            value={draft.plannedCycles}
            onChange={(e) => onChange({ ...draft, plannedCycles: e.target.value })}
          />
        </label>
      </div>
      <fieldset className="flex flex-col gap-1 text-sm text-gray-700">
        <legend>{t('goals.materials.subjectsLabel')}</legend>
        <div className="flex flex-wrap gap-3">
          {subjects.map((subject) => (
            <label key={subject.name} className="flex items-center gap-1">
              <input
                type="checkbox"
                checked={draft.subjectNames.includes(subject.name)}
                onChange={() => toggleSubject(subject.name)}
              />
              {subject.name || t('goals.examWizard.step3.unnamedSubject')}
            </label>
          ))}
        </div>
      </fieldset>
    </Card>
  )
}

/** ウィザードStep3（教材を確認する。仕様書「資格モードの作成ウィザード」）。 */
export function Step3Materials({
  materials,
  subjects,
  onChangeMaterials,
}: {
  materials: ExamMaterialDraft[]
  subjects: ExamSubjectDraft[]
  onChangeMaterials: (next: ExamMaterialDraft[]) => void
}) {
  return (
    <div className="flex flex-col gap-3">
      <p className="text-sm text-gray-600">{t('goals.examWizard.step3.description')}</p>
      <p className="text-xs text-amber-700">{t('goals.examWizard.templateAmountDisclaimer')}</p>

      {materials.map((draft, index) => (
        // eslint-disable-next-line react/no-array-index-key -- 教材名は編集途中で重複しうるため
        <MaterialDraftRow
          key={index}
          draft={draft}
          subjects={subjects}
          onChange={(next) =>
            onChangeMaterials(materials.map((item, itemIndex) => (itemIndex === index ? next : item)))
          }
          onRemove={() => onChangeMaterials(materials.filter((_, itemIndex) => itemIndex !== index))}
        />
      ))}

      <Button
        type="button"
        variant="secondary"
        onClick={() => onChangeMaterials([...materials, emptyMaterialDraft()])}
      >
        {t('goals.examWizard.step3.addMaterial')}
      </Button>
    </div>
  )
}
