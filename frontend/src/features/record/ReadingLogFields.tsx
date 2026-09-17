import { t } from '../../locales/t'
import { Card } from '../../components/Card'
import { Input } from '../../components/Input'
import { Textarea } from '../../components/Textarea'
import type { BookRead } from '../../api/goals'
import { PreviousEntryHint } from './PreviousEntryHint'
import { usePreviousReadingLogEntry } from './usePreviousEntryQueries'
import { SlotMinutesFields } from './SlotMinutesFields'
import type { SlotMinutesFormValue } from './slotMinutesForm'
import { getReadingLogQuestions, type ReadingLogFormValue } from './readingLogForm'

type ReadingLogFieldsProps = {
  /** 「前回はこう書いていました」ヒントの取得に使う対象日。 */
  targetDate: string
  books: BookRead[]
  values: Record<number, ReadingLogFormValue>
  onChangeField: (bookId: number, field: keyof ReadingLogFormValue, value: string | string[]) => void
  /** 時間枠ごとの読書時間の変更（読書も配分の対象。要件定義書R-64）。 */
  onChangeSlotMinutes: (bookId: number, slotMinutes: SlotMinutesFormValue) => void
  /** 追加候補の全時間枠（slot_id → 名称）。 */
  slotNames: Map<number, string>
}

/** 想起入力欄（書籍別の想起本文・任意の現在ページ）。SC-06の読書用実績入力
 * （仕様書6.5「読書目標の実績入力」、要件定義書R-65）。StudyLogFieldsと対になる。
 * 資格試験と異なり日次ノルマは持たないため、書名・読了目標日までの残日数のみ表示する。 */
export function ReadingLogFields({
  targetDate,
  books,
  values,
  onChangeField,
  onChangeSlotMinutes,
  slotNames,
}: ReadingLogFieldsProps) {
  if (books.length === 0) {
    return null
  }
  const questions = getReadingLogQuestions()

  return (
    <div className="flex flex-col gap-3">
      {books.map((book) => {
        const value = values[book.id]
        if (!value) {
          return null
        }
        return (
          <ReadingLogFieldsCard
            key={book.id}
            targetDate={targetDate}
            book={book}
            questions={questions}
            value={value}
            slotNames={slotNames}
            onChangeField={onChangeField}
            onChangeSlotMinutes={onChangeSlotMinutes}
          />
        )
      })}
    </div>
  )
}

/** 1書籍分のカード。前回ヒントの取得はBookの数だけ呼び出す必要があるため、
 * フックのルール上ループの外へ切り出す（DiaryFields.DiaryFieldsCardと同じ方針）。 */
function ReadingLogFieldsCard({
  targetDate,
  book,
  questions,
  value,
  slotNames,
  onChangeField,
  onChangeSlotMinutes,
}: {
  targetDate: string
  book: BookRead
  questions: string[]
  value: ReadingLogFormValue
  slotNames: Map<number, string>
  onChangeField: ReadingLogFieldsProps['onChangeField']
  onChangeSlotMinutes: ReadingLogFieldsProps['onChangeSlotMinutes']
}) {
  const previousEntry = usePreviousReadingLogEntry(targetDate, book.id)

  return (
    <Card>
      <div className="flex items-center justify-between">
        <p className="font-medium text-gray-900">{book.title}</p>
        <p className="text-sm text-gray-500">
          {t('dailyReport.readingLog.remainingDays', { days: book.remaining_days })}
        </p>
      </div>
      <div className="mt-2">
        <PreviousEntryHint entry={previousEntry.data} />
      </div>
      {questions.map((question, index) => (
        <label key={index} className="mt-2 flex flex-col gap-1 text-xs text-gray-600">
          {question}
          <Textarea
            rows={2}
            placeholder={t('dailyReport.questionAnswerPlaceholder')}
            value={value.questionAnswers[index] ?? ''}
            onChange={(e) => {
              const next = [...value.questionAnswers]
              next[index] = e.target.value
              onChangeField(book.id, 'questionAnswers', next)
            }}
          />
        </label>
      ))}
      <p className="mt-2 text-xs text-gray-400">{t('dailyReport.voiceInputHint')}</p>
      <label className="mt-2 flex flex-col gap-1 text-xs text-gray-600">
        {t('dailyReport.readingLog.recallLabel')}
        <Textarea
          rows={4}
          placeholder={t('dailyReport.readingLog.recallPlaceholder')}
          value={value.freeText}
          onChange={(e) => onChangeField(book.id, 'freeText', e.target.value)}
        />
      </label>
      <SlotMinutesFields
        label={t('dailyReport.readingLog.slotMinutesLabel')}
        defaults={[]}
        values={value.slotMinutes}
        addedSlotIds={Object.keys(value.slotMinutes).map(Number)}
        slotNames={slotNames}
        onChange={(slotId, minutes) =>
          onChangeSlotMinutes(book.id, { ...value.slotMinutes, [slotId]: minutes })
        }
        onAddSlot={(slotId) => onChangeSlotMinutes(book.id, { ...value.slotMinutes, [slotId]: '' })}
      />
      <label className="mt-2 flex flex-col gap-1 text-xs text-gray-600">
        {t('dailyReport.readingLog.currentPageLabel', { total: book.total_pages })}
        <Input
          type="number"
          min={0}
          max={book.total_pages}
          value={value.currentPage}
          onChange={(e) => onChangeField(book.id, 'currentPage', e.target.value)}
        />
      </label>
    </Card>
  )
}
