import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { t } from '../../locales/t'
import { Card } from '../../components/Card'
import { Button } from '../../components/Button'
import { Input } from '../../components/Input'
import { Textarea } from '../../components/Textarea'
import { ExpandableText } from '../../components/ExpandableText'
import { useToast } from '../../components/toastContext'
import { apiErrorMessage } from '../../api/client'
import {
  checkVocabCard,
  createVocabCard,
  deleteVocabCard,
  getVocabCards,
  updateVocabCard,
  type VocabCard,
  type VocabCardType,
} from '../../api/vocab'
import { QUERY_KEYS } from '../../constants/queryKeys'
import { CardTypeFilterSelect } from './CardTypeFilterSelect'
import { VOCAB_CARD_FILTER_KEYS, type VocabCardFilterKey, type VocabCardTypeKey } from './vocabCardFilters'

const SORTS = ['REGISTERED', 'ACCURACY_ASC', 'INCORRECT_COUNT_DESC', 'CONSECUTIVE_WRONG_DESC'] as const

function formatAccuracy(accuracyPercent: number | null): string {
  return accuracyPercent === null ? '—' : `${Math.round(accuracyPercent)}%`
}

type VocabCardFormFieldsProps = {
  term: string
  setTerm: (value: string) => void
  meaning: string
  setMeaning: (value: string) => void
  note: string
  setNote: (value: string) => void
}

/** 用語カードの入力欄（用語・意味・別名・補足、開発Todo_単語帳_v1.0 要件A〜D）。
 * `VocabCardForm`を100行以内に保つための分離（CODING_RULES.md「保守性」）。 */
function TermCardFields({
  term,
  setTerm,
  meaning,
  setMeaning,
  aliases,
  setAliases,
  note,
  setNote,
}: VocabCardFormFieldsProps & { aliases: string; setAliases: (value: string) => void }) {
  return (
    <>
      <label className="flex flex-col gap-1 text-sm text-text-secondary">
        {t('vocab.deckDetail.termLabel')}
        <Input value={term} onChange={(e) => setTerm(e.target.value)} required />
      </label>
      <label className="flex flex-col gap-1 text-sm text-text-secondary">
        {t('vocab.deckDetail.meaningLabel')}
        <Textarea value={meaning} onChange={(e) => setMeaning(e.target.value)} rows={2} required />
      </label>
      <label className="flex flex-col gap-1 text-sm text-text-secondary">
        {t('vocab.deckDetail.aliasesLabel')}
        <Textarea
          value={aliases}
          onChange={(e) => setAliases(e.target.value)}
          rows={2}
          placeholder={t('vocab.deckDetail.aliasesHint')}
        />
      </label>
      <label className="flex flex-col gap-1 text-sm text-text-secondary">
        {t('vocab.deckDetail.noteLabel')}
        <Textarea value={note} onChange={(e) => setNote(e.target.value)} rows={2} />
      </label>
    </>
  )
}

/** シチュエーションカードの入力欄（見出し・状況・問い・最善の対応・解説、開発Todo_単語帳_v1.0
 * 要件F F-U1）。`VocabCardForm`を100行以内に保つための分離。 */
function SituationCardFields({
  term,
  setTerm,
  meaning,
  setMeaning,
  note,
  setNote,
  situationText,
  setSituationText,
  questionText,
  setQuestionText,
}: VocabCardFormFieldsProps & {
  situationText: string
  setSituationText: (value: string) => void
  questionText: string
  setQuestionText: (value: string) => void
}) {
  return (
    <>
      <label className="flex flex-col gap-1 text-sm text-text-secondary">
        {t('vocab.deckDetail.headingLabel')}
        <Input value={term} onChange={(e) => setTerm(e.target.value)} required />
      </label>
      <label className="flex flex-col gap-1 text-sm text-text-secondary">
        {t('vocab.deckDetail.situationTextLabel')}
        <Textarea
          value={situationText}
          onChange={(e) => setSituationText(e.target.value)}
          rows={4}
          required
        />
      </label>
      <label className="flex flex-col gap-1 text-sm text-text-secondary">
        {t('vocab.deckDetail.questionTextLabel')}
        <Textarea
          value={questionText}
          onChange={(e) => setQuestionText(e.target.value)}
          rows={2}
          placeholder={t('vocab.deckDetail.questionTextHint')}
        />
      </label>
      <label className="flex flex-col gap-1 text-sm text-text-secondary">
        {t('vocab.deckDetail.bestActionLabel')}
        <Textarea value={meaning} onChange={(e) => setMeaning(e.target.value)} rows={2} required />
      </label>
      <label className="flex flex-col gap-1 text-sm text-text-secondary">
        {t('vocab.deckDetail.explanationLabel')}
        <Textarea value={note} onChange={(e) => setNote(e.target.value)} rows={3} />
      </label>
    </>
  )
}

/** 追加・編集フォーム（開発Todo_単語帳_v1.0 要件F）。種類は追加時にだけ選べる
 * （既存カードの種類は不変、F-D2。編集フォームは項目構成が種類ごとに異なる）。 */
function VocabCardForm({
  deckId,
  card,
  onDone,
}: {
  deckId: number
  card?: VocabCard
  onDone: () => void
}) {
  const queryClient = useQueryClient()
  const { showApiError } = useToast()
  const [cardType, setCardType] = useState<VocabCardType>(card?.card_type ?? 'TERM')
  const [term, setTerm] = useState(card?.term ?? '')
  const [meaning, setMeaning] = useState(card?.meaning ?? '')
  const [aliases, setAliases] = useState(card?.aliases ?? '')
  const [note, setNote] = useState(card?.note ?? '')
  const [situationText, setSituationText] = useState(card?.situation_text ?? '')
  const [questionText, setQuestionText] = useState(card?.question_text ?? '')

  const mutation = useMutation({
    mutationFn: () => {
      const common = { term, meaning, note: note || null }
      const payload =
        cardType === 'TERM'
          ? { ...common, aliases: aliases || null }
          : { ...common, situation_text: situationText, question_text: questionText || null }
      return card
        ? updateVocabCard(card.id, payload)
        : createVocabCard(deckId, { ...payload, card_type: cardType })
    },
    meta: { overlay: 'saving' },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.vocabCards(deckId) })
      onDone()
    },
    onError: showApiError,
  })

  return (
    <form
      className="flex flex-col gap-3"
      onSubmit={(event) => {
        event.preventDefault()
        mutation.mutate()
      }}
    >
      {card ? (
        <p className="text-xs text-text-faint">
          {t('vocab.deckDetail.cardTypeLabel')}:{' '}
          {t(`vocab.deckDetail.cardTypeOptions.${card.card_type}`)}（
          {t('vocab.deckDetail.cardTypeFixedNotice')}）
        </p>
      ) : (
        <label className="flex flex-col gap-1 text-sm text-text-secondary">
          {t('vocab.deckDetail.cardTypeLabel')}
          <select
            className="rounded-md border border-border-strong px-3 py-2 text-sm"
            value={cardType}
            onChange={(e) => setCardType(e.target.value as VocabCardType)}
          >
            <option value="TERM">{t('vocab.deckDetail.cardTypeOptions.TERM')}</option>
            <option value="SITUATION">{t('vocab.deckDetail.cardTypeOptions.SITUATION')}</option>
          </select>
        </label>
      )}

      {cardType === 'TERM' ? (
        <TermCardFields
          term={term}
          setTerm={setTerm}
          meaning={meaning}
          setMeaning={setMeaning}
          aliases={aliases}
          setAliases={setAliases}
          note={note}
          setNote={setNote}
        />
      ) : (
        <SituationCardFields
          term={term}
          setTerm={setTerm}
          meaning={meaning}
          setMeaning={setMeaning}
          note={note}
          setNote={setNote}
          situationText={situationText}
          setSituationText={setSituationText}
          questionText={questionText}
          setQuestionText={setQuestionText}
        />
      )}

      <div className="flex justify-end gap-2">
        <Button type="button" variant="secondary" onClick={onDone}>
          {t('common.action.cancel')}
        </Button>
        <Button type="submit" disabled={mutation.isPending}>
          {t('common.action.save')}
        </Button>
      </div>
    </form>
  )
}

function VocabCardRow({ deckId, card }: { deckId: number; card: VocabCard }) {
  const queryClient = useQueryClient()
  const { showApiError } = useToast()
  const [editing, setEditing] = useState(false)

  const invalidate = () => queryClient.invalidateQueries({ queryKey: QUERY_KEYS.vocabCards(deckId) })

  const checkMutation = useMutation({
    mutationFn: (isChecked: boolean) => checkVocabCard(card.id, isChecked),
    onSuccess: invalidate,
    onError: showApiError,
  })
  const deleteMutation = useMutation({
    mutationFn: () => deleteVocabCard(card.id),
    meta: { overlay: 'deleting' },
    onSuccess: invalidate,
    onError: showApiError,
  })

  if (editing) {
    return (
      <Card>
        <VocabCardForm deckId={deckId} card={card} onDone={() => setEditing(false)} />
      </Card>
    )
  }

  return (
    <Card className="flex items-start justify-between gap-3">
      <label className="mt-1 flex items-center">
        <input
          type="checkbox"
          checked={card.is_checked}
          onChange={(e) => checkMutation.mutate(e.target.checked)}
          aria-label={t('vocab.deckDetail.checkedLabel')}
        />
      </label>
      <div className="flex-1">
        <p className="flex items-center gap-2 text-sm font-medium text-text-primary">
          <span className="rounded-full bg-surface-muted px-2 py-0.5 text-xs text-text-faint">
            {t(`vocab.deckDetail.cardTypeOptions.${card.card_type}`)}
          </span>
          {card.term}
          {card.is_mastered && (
            <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-xs font-medium text-emerald-800">
              {t('vocab.deckDetail.masteredBadge')}
            </span>
          )}
        </p>
        <ExpandableText
          text={card.card_type === 'TERM' ? card.meaning : card.situation_text}
          className="text-sm text-text-secondary"
        />
        <p className="mt-1 text-xs text-text-faint">
          {t('vocab.deckDetail.statsLine', {
            correct: card.correct_count,
            incorrect: card.incorrect_count,
            accuracy: formatAccuracy(card.accuracy_percent),
            streak: card.consecutive_incorrect,
          })}
        </p>
      </div>
      <div className="flex gap-2">
        <Button variant="secondary" onClick={() => setEditing(true)}>
          {t('common.action.edit')}
        </Button>
        <Button
          variant="secondary"
          onClick={() => {
            if (window.confirm(t('common.confirmDelete'))) {
              deleteMutation.mutate()
            }
          }}
        >
          {t('common.action.delete')}
        </Button>
      </div>
    </Card>
  )
}

/** 単語帳詳細のカード一覧（絞り込み・並び替え・CRUD・チェック切り替え）。種類の絞り込み
 * （開発Todo_単語帳_v1.0 要件F F-U1「機能1」）を成績の絞り込みと独立に持つ。 */
export function VocabCardList({ deckId }: { deckId: number }) {
  const [filter, setFilter] = useState<VocabCardFilterKey>('ALL')
  const [cardTypeFilter, setCardTypeFilter] = useState<VocabCardTypeKey>('ALL')
  const [sort, setSort] = useState<(typeof SORTS)[number]>('REGISTERED')
  const [addOpen, setAddOpen] = useState(false)

  const cardsQuery = useQuery({
    queryKey: QUERY_KEYS.vocabCardsFiltered(deckId, filter, sort, cardTypeFilter),
    queryFn: () =>
      getVocabCards(deckId, filter, sort, cardTypeFilter === 'ALL' ? undefined : cardTypeFilter),
  })

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap gap-3">
        <CardTypeFilterSelect
          label={t('vocab.deckDetail.cardTypeFilterLabel')}
          value={cardTypeFilter}
          onChange={setCardTypeFilter}
        />
        <label className="flex flex-col gap-1 text-sm text-text-secondary">
          {t('vocab.deckDetail.filterLabel')}
          <select
            className="rounded-md border border-border-strong px-3 py-2 text-sm"
            value={filter}
            onChange={(e) => setFilter(e.target.value as VocabCardFilterKey)}
          >
            {VOCAB_CARD_FILTER_KEYS.map((key) => (
              <option key={key} value={key}>
                {t(`vocab.deckDetail.filterOptions.${key}`)}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-sm text-text-secondary">
          {t('vocab.deckDetail.sortLabel')}
          <select
            className="rounded-md border border-border-strong px-3 py-2 text-sm"
            value={sort}
            onChange={(e) => setSort(e.target.value as (typeof SORTS)[number])}
          >
            {SORTS.map((key) => (
              <option key={key} value={key}>
                {t(`vocab.deckDetail.sortOptions.${key}`)}
              </option>
            ))}
          </select>
        </label>
      </div>

      {cardsQuery.isLoading && <p className="text-sm text-text-faint">{t('common.loading')}</p>}
      {cardsQuery.isError && (
        <p className="text-sm text-danger-text">{apiErrorMessage(cardsQuery.error)}</p>
      )}
      {cardsQuery.data?.length === 0 && (
        <p className="text-sm text-text-faint">{t('vocab.deckDetail.cardsEmpty')}</p>
      )}

      {cardsQuery.data?.map((card: VocabCard) => (
        <VocabCardRow key={card.id} deckId={deckId} card={card} />
      ))}

      {addOpen ? (
        <Card>
          <VocabCardForm deckId={deckId} onDone={() => setAddOpen(false)} />
        </Card>
      ) : (
        <Button variant="secondary" onClick={() => setAddOpen(true)}>
          {t('vocab.deckDetail.addCardTitle')}
        </Button>
      )}
    </div>
  )
}
