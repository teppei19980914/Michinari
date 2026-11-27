import { useState } from 'react'
import { t } from '../../locales/t'
import { Card } from '../../components/Card'
import { Button } from '../../components/Button'
import { Input } from '../../components/Input'
import type { VocabCardTypeFilter, VocabQuizMode } from '../../api/vocab'
import { CardTypeFilterSelect } from './CardTypeFilterSelect'
import { VOCAB_CARD_FILTER_KEYS, type VocabCardFilterKey, type VocabCardTypeKey } from './vocabCardFilters'

const MODES: VocabQuizMode[] = [
  'FLASH_TERM_TO_MEANING',
  'FLASH_MEANING_TO_TERM',
  'FLASH_RANDOM',
  'TYPED_MEANING_TO_TERM',
  'CHOICE_TERM_TO_MEANING',
  'CHOICE_MEANING_TO_TERM',
  'CHOICE_RANDOM',
]
const CHOICE_MODES: VocabQuizMode[] = [
  'CHOICE_TERM_TO_MEANING',
  'CHOICE_MEANING_TO_TERM',
  'CHOICE_RANDOM',
]
const ORDERS = ['RANDOM', 'WEAK_ORDER', 'REGISTERED'] as const

export type VocabQuizSessionParams = {
  mode: VocabQuizMode
  filter: string
  order: string
  question_count: number
  card_type: VocabCardTypeFilter
}

/** 出題セッションの開始条件フォーム（カードの種類・出題形式・絞り込み・並び順・問題数）。
 * `defaultQuestionCount`・`maxQuestionCount`は単語帳詳細のレスポンス（`vocab.
 * session_default_questions`・`vocab.session_max_questions`、設定画面には表示しない内部
 * パラメータ）を初期値・入力欄の上限として使う（軽微1の修正、2026-11-22）。`termCardCount`
 * は4択の可否判定に使う（用語カードだけで数える、開発Todo_単語帳_v1.0 要件F F-U3・F-D8）。 */
export function VocabQuizSetupForm({
  termCardCount,
  defaultQuestionCount,
  maxQuestionCount,
  onStart,
}: {
  termCardCount: number
  defaultQuestionCount: number
  maxQuestionCount: number
  onStart: (params: VocabQuizSessionParams) => void
}) {
  const [cardType, setCardType] = useState<VocabCardTypeKey>('ALL')
  const [mode, setMode] = useState<VocabQuizMode>('FLASH_TERM_TO_MEANING')
  const [filter, setFilter] = useState<VocabCardFilterKey>('ALL')
  const [order, setOrder] = useState<(typeof ORDERS)[number]>('RANDOM')
  const [questionCount, setQuestionCount] = useState(defaultQuestionCount)
  const choiceUnavailable = termCardCount < 4

  return (
    <Card className="flex flex-col gap-4">
      <CardTypeFilterSelect
        label={t('vocab.deckDetail.cardTypeFilterLabel')}
        value={cardType}
        onChange={setCardType}
      />

      <label className="flex flex-col gap-1 text-sm text-text-secondary">
        {t('vocab.quiz.modeLabel')}
        <select
          className="rounded-md border border-border-strong px-3 py-2 text-sm"
          value={mode}
          onChange={(e) => setMode(e.target.value as VocabQuizMode)}
        >
          {MODES.map((key) => (
            <option key={key} value={key} disabled={choiceUnavailable && CHOICE_MODES.includes(key)}>
              {t(`vocab.quiz.modeOptions.${key}`)}
            </option>
          ))}
        </select>
        {choiceUnavailable && (
          <span className="text-xs text-text-faint">{t('vocab.quiz.choiceUnavailableNotice')}</span>
        )}
      </label>

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
        {t('vocab.quiz.orderLabel')}
        <select
          className="rounded-md border border-border-strong px-3 py-2 text-sm"
          value={order}
          onChange={(e) => setOrder(e.target.value as (typeof ORDERS)[number])}
        >
          {ORDERS.map((key) => (
            <option key={key} value={key}>
              {t(`vocab.quiz.orderOptions.${key}`)}
            </option>
          ))}
        </select>
      </label>

      <label className="flex flex-col gap-1 text-sm text-text-secondary">
        {t('vocab.quiz.questionCountLabel')}
        <Input
          type="number"
          min={1}
          max={maxQuestionCount}
          value={questionCount}
          onChange={(e) => setQuestionCount(Number(e.target.value))}
        />
      </label>

      <Button
        onClick={() =>
          onStart({ mode, filter, order, question_count: questionCount, card_type: cardType })
        }
      >
        {t('vocab.quiz.startButton')}
      </Button>
    </Card>
  )
}
