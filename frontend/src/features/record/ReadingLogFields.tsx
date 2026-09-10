import { t } from '../../locales/t'
import { Card } from '../../components/Card'
import { Input } from '../../components/Input'
import { Textarea } from '../../components/Textarea'
import type { BookRead } from '../../api/goals'
import { SlotMinutesFields } from './SlotMinutesFields'
import type { SlotMinutesFormValue } from './slotMinutesForm'
import type { ReadingLogFormValue } from './readingLogForm'

type ReadingLogFieldsProps = {
  books: BookRead[]
  values: Record<number, ReadingLogFormValue>
  onChangeField: (bookId: number, field: keyof ReadingLogFormValue, value: string) => void
  /** 時間枠ごとの読書時間の変更（読書も配分の対象。要件定義書R-64）。 */
  onChangeSlotMinutes: (bookId: number, slotMinutes: SlotMinutesFormValue) => void
  /** 追加候補の全時間枠（slot_id → 名称）。 */
  slotNames: Map<number, string>
}

/** 想起入力欄（書籍別の想起本文・任意のページ数）。SC-06の読書用実績入力
 * （仕様書6.5「読書目標の実績入力」、要件定義書R-65）。StudyLogFieldsと対になる。
 * 資格試験と異なり日次ノルマは持たないため、書名・読了目標日までの残日数のみ表示する。 */
export function ReadingLogFields({
  books,
  values,
  onChangeField,
  onChangeSlotMinutes,
  slotNames,
}: ReadingLogFieldsProps) {
  if (books.length === 0) {
    return null
  }

  return (
    <div className="flex flex-col gap-3">
      {books.map((book) => {
        const value = values[book.id]
        if (!value) {
          return null
        }
        return (
          <Card key={book.id}>
            <div className="flex items-center justify-between">
              <p className="font-medium text-gray-900">{book.title}</p>
              <p className="text-sm text-gray-500">
                {t('dailyReport.readingLog.remainingDays', { days: book.remaining_days })}
              </p>
            </div>
            <label className="mt-2 flex flex-col gap-1 text-xs text-gray-600">
              {t('dailyReport.readingLog.recallLabel')}
              <Textarea
                rows={4}
                placeholder={t('dailyReport.readingLog.recallPlaceholder')}
                value={value.recallBody}
                onChange={(e) => onChangeField(book.id, 'recallBody', e.target.value)}
              />
            </label>
            <SlotMinutesFields
              defaults={[]}
              values={value.slotMinutes}
              addedSlotIds={Object.keys(value.slotMinutes).map(Number)}
              slotNames={slotNames}
              onChange={(slotId, minutes) =>
                onChangeSlotMinutes(book.id, { ...value.slotMinutes, [slotId]: minutes })
              }
              onAddSlot={(slotId) =>
                onChangeSlotMinutes(book.id, { ...value.slotMinutes, [slotId]: '' })
              }
            />
            <div className="mt-2 grid grid-cols-2 gap-2">
              <label className="flex flex-col gap-1 text-xs text-gray-600">
                {t('dailyReport.readingLog.pagesReadLabel')}
                <Input
                  type="number"
                  min={0}
                  value={value.pagesRead}
                  onChange={(e) => onChangeField(book.id, 'pagesRead', e.target.value)}
                />
              </label>
              {book.total_pages !== null && (
                <label className="flex flex-col gap-1 text-xs text-gray-600">
                  {t('dailyReport.readingLog.currentPageLabel', { total: book.total_pages })}
                  <Input
                    type="number"
                    min={0}
                    max={book.total_pages}
                    value={value.currentPage}
                    onChange={(e) => onChangeField(book.id, 'currentPage', e.target.value)}
                  />
                </label>
              )}
            </div>
          </Card>
        )
      })}
    </div>
  )
}
