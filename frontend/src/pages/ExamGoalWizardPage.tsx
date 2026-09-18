import { t } from '../locales/t'
import { Button } from '../components/Button'
import { totalMinutes } from '../features/goal/slotAllocationForm'
import { Step1SelectTemplate } from '../features/goal/examWizard/Step1SelectTemplate'
import { Step2SubjectsAndDates } from '../features/goal/examWizard/Step2SubjectsAndDates'
import { Step3Materials } from '../features/goal/examWizard/Step3Materials'
import { Step4TimeSlots } from '../features/goal/examWizard/Step4TimeSlots'
import { Step5Confirm } from '../features/goal/examWizard/Step5Confirm'
import { canProceedFromMaterials, canProceedFromSubjects } from '../features/goal/examWizard/examWizardValidation'
import { useExamGoalWizard, type WizardStep } from '../features/goal/examWizard/useExamGoalWizard'

const TOTAL_STEPS = 5

function renderWizardStep(wizard: ReturnType<typeof useExamGoalWizard>) {
  switch (wizard.step) {
    case 1:
      return (
        <Step1SelectTemplate
          templates={wizard.templatesQuery.data ?? []}
          isLoading={wizard.templatesQuery.isLoading}
          selection={wizard.selection}
          examName={wizard.examName}
          onSelectTemplate={wizard.selectTemplate}
          onSelectOther={wizard.selectOther}
          onChangeExamName={wizard.setExamName}
        />
      )
    case 2:
      return <Step2SubjectsAndDates subjects={wizard.subjects} onChangeSubjects={wizard.setSubjects} />
    case 3:
      return (
        <Step3Materials
          materials={wizard.materials}
          subjects={wizard.subjects}
          onChangeMaterials={wizard.setMaterials}
        />
      )
    case 4:
      return (
        <Step4TimeSlots
          rows={wizard.slotRows}
          values={wizard.slotValues}
          onChangeMinutes={wizard.setSlotMinutes}
          weekdayHours={wizard.weekdayHours}
          weekendHours={wizard.weekendHours}
          onChangeWeekdayHours={wizard.setWeekdayHours}
          onChangeWeekendHours={wizard.setWeekendHours}
        />
      )
    case 5:
      return (
        <Step5Confirm examName={wizard.examName} subjects={wizard.subjects} materials={wizard.materials} />
      )
  }
}

function canProceedFromCurrentStep(wizard: ReturnType<typeof useExamGoalWizard>): boolean {
  switch (wizard.step) {
    case 1:
      return wizard.examName.trim() !== ''
    case 2:
      return canProceedFromSubjects(wizard.subjects)
    case 3:
      return canProceedFromMaterials(wizard.materials)
    case 4:
      return wizard.hasExistingSlots
        ? totalMinutes(wizard.slotValues) > 0
        : (Number(wizard.weekdayHours) || 0) > 0 || (Number(wizard.weekendHours) || 0) > 0
    case 5:
      return true
  }
}

/** SC-?? 資格モードの作成ウィザード（仕様書「資格モードの作成ウィザード」）。
 * 既存の目標詳細画面（GoalDetailPage）を置き換えるものではなく、作成経路を1つ追加する
 * ものである。状態とAPI呼び出しは`useExamGoalWizard`に集約し、ここでは描画のみを行う。 */
export function ExamGoalWizardPage() {
  const wizard = useExamGoalWizard()
  const nextHandlers = {
    1: wizard.goToStep2,
    2: wizard.goToStep3,
    3: wizard.goToStep4,
    4: wizard.goToStep5,
  } as const

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-4 p-4">
      <h1 className="text-xl font-semibold text-gray-900">{t('goals.examWizard.title')}</h1>
      <p className="text-sm text-gray-500">
        {t('goals.examWizard.stepIndicator', { current: wizard.step, total: TOTAL_STEPS })}
      </p>

      {renderWizardStep(wizard)}

      <div className="mt-2 flex justify-between">
        <Button
          type="button"
          variant="secondary"
          disabled={wizard.step === 1}
          onClick={() => wizard.setStep((wizard.step - 1) as WizardStep)}
        >
          {t('common.action.back')}
        </Button>
        {wizard.step === 5 ? (
          <Button disabled={wizard.isSubmitting} onClick={wizard.activate}>
            {t('goals.examWizard.startButton')}
          </Button>
        ) : (
          <Button
            disabled={!canProceedFromCurrentStep(wizard) || wizard.isSubmitting}
            onClick={nextHandlers[wizard.step]}
          >
            {t('common.action.next')}
          </Button>
        )}
      </div>
    </div>
  )
}
