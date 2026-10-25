/** 目標相談チャットのタブ（S09で資格目標向けに導入、S10で読書・仕事へ展開、S11で会話継続に
 * 対応）。
 *
 * 目標詳細画面に常設する（ヘルプの全画面浮動ボタンとは別系統、開発Todo U2）。
 * S11以降、質問は「会話」単位で送る（直近往復をプロンプトに含める、開発Todo v1.2）。
 * 会話の選択・新規作成・削除・自動作成は`useActiveGoalConsultationConversation`に集約する
 * （CODING_RULES.md「フロントの分岐は.tsへ切り出す」、関数の行数を抑える目的もある）。
 * 画面に積む「今回の」履歴（state）は会話を切り替える・新規作成するまでの間だけ保持するが、
 * 質問・回答自体は`goal_consultation_log`へ永続化されるため、相談履歴セクション
 * （`GoalConsultationHistory`）からは他のタブへ切り替えて戻っても参照できる（S10、開発Todo
 * v1.1 V6）。 */
import { useEffect, useRef, useState, type FormEvent, type RefObject } from 'react'
import type { GoalCategory } from '../../api/goals'
import { ApiError } from '../../api/client'
import type { GoalConsultationAnswer } from '../../api/goalConsultation'
import { AiUnconfiguredNotice } from '../../components/AiUnconfiguredNotice'
import { Button } from '../../components/Button'
import { Card } from '../../components/Card'
import { Textarea } from '../../components/Textarea'
import { useAiConfigured } from '../../hooks/useAiConfigured'
import { t } from '../../locales/t'
import { AttachmentPicker } from '../attachment/AttachmentPicker'
import {
  conversationDisplayTitle,
  errorMessageKey,
  questionExampleKeys,
  validateQuestion,
} from './goalConsultationLogic'
import { GoalConsultationAnswerBody } from './GoalConsultationAnswer'
import { GoalConsultationHistory } from './GoalConsultationHistory'
import {
  useActiveGoalConsultationConversation,
  useAskGoalConsultationQuestion,
  useGoalConsultationLimits,
} from './useGoalConsultation'

/** 画面に積む履歴の1件。質問・回答・エラーのいずれか。 */
type HistoryEntry =
  | { kind: 'question'; id: number; text: string }
  | { kind: 'answer'; id: number; answer: GoalConsultationAnswer }
  | { kind: 'error'; id: number; messageKey: string }

type GoalConsultationTabProps = {
  goalId: number
  category: GoalCategory
}

/** 質問の入力欄の下に出す検証メッセージ（上限が読めるまでは出さない）。 */
function validationMessage(draft: string, maxChars: number | undefined): string | null {
  if (maxChars === undefined) return null
  const error = validateQuestion(draft, maxChars)
  if (error === 'tooLong') return t('goalConsultation.tooLong', { max: maxChars })
  return null
}

/** 履歴の1件を描画する。 */
function HistoryItem({ entry }: { entry: HistoryEntry }) {
  if (entry.kind === 'question') {
    return (
      <div className="ml-auto max-w-[85%] rounded-md bg-accent-muted-bg p-2 text-sm text-text-primary">
        <p className="mb-1 text-xs text-text-faint">{t('goalConsultation.userLabel')}</p>
        <p className="whitespace-pre-wrap">{entry.text}</p>
      </div>
    )
  }
  return (
    <div className="max-w-[85%] rounded-md bg-surface-muted p-2">
      <p className="mb-1 text-xs text-text-faint">{t('goalConsultation.assistantLabel')}</p>
      {entry.kind === 'answer' ? (
        <GoalConsultationAnswerBody answer={entry.answer} />
      ) : (
        <p className="text-sm text-text-secondary">{t(entry.messageKey)}</p>
      )}
    </div>
  )
}

/** 画面に積んだ履歴（今回の往復）の表示欄。 */
function ConsultationThread({
  historyRef,
  history,
  pending,
}: {
  historyRef: RefObject<HTMLDivElement | null>
  history: HistoryEntry[]
  pending: boolean
}) {
  return (
    <div ref={historyRef} className="flex max-h-96 flex-col gap-2 overflow-y-auto">
      {history.length === 0 && (
        <p className="text-sm text-text-faint">{t('goalConsultation.noHistoryYet')}</p>
      )}
      {history.map((entry) => (
        <HistoryItem key={entry.id} entry={entry} />
      ))}
      {pending && <p className="text-sm text-text-faint">{t('goalConsultation.sending')}</p>}
    </div>
  )
}

/** 質問例ボタン・入力欄・送信ボタン。 */
function QuestionInputForm({
  onSubmit,
  exampleKeys,
  draft,
  setDraft,
  warning,
  canSend,
  pending,
  selectedAttachmentIds,
  setSelectedAttachmentIds,
}: {
  onSubmit: (event: FormEvent<HTMLFormElement>) => void
  exampleKeys: string[]
  draft: string
  setDraft: (value: string) => void
  warning: string | null
  canSend: boolean
  pending: boolean
  selectedAttachmentIds: number[]
  setSelectedAttachmentIds: (ids: number[]) => void
}) {
  return (
    <form onSubmit={onSubmit} className="flex flex-col gap-2">
      {/* 質問例ボタン（目標の種類ごと、開発Todo v1.1 要件2）。クリックで入力欄に
          差し込むだけで、送信は利用者の操作に委ねる（即時送信しない）。 */}
      <div className="flex flex-wrap gap-2">
        {exampleKeys.map((key) => (
          <button
            key={key}
            type="button"
            disabled={pending}
            onClick={() => setDraft(t(key))}
            className="rounded-full border border-border px-3 py-1 text-xs text-text-secondary hover:bg-surface-muted"
          >
            {t(key)}
          </button>
        ))}
      </div>
      <Textarea
        aria-label={t('goalConsultation.placeholder')}
        placeholder={t('goalConsultation.placeholder')}
        value={draft}
        rows={3}
        disabled={pending}
        onChange={(event) => setDraft(event.target.value)}
      />
      <AttachmentPicker selectedIds={selectedAttachmentIds} onChange={setSelectedAttachmentIds} />
      {warning && <p className="text-xs text-danger-text">{warning}</p>}
      <Button type="submit" disabled={!canSend}>
        {t('goalConsultation.send')}
      </Button>
    </form>
  )
}

/** 会話の選択・新規開始・削除（S11、開発Todo v1.2 W7）。 */
function ConversationSwitcher({
  conversations,
  activeConversationId,
  onSelect,
  onCreate,
  onDelete,
  busy,
}: {
  conversations: { id: number; title: string }[]
  activeConversationId: number | null
  onSelect: (id: number) => void
  onCreate: () => void
  onDelete: () => void
  busy: boolean
}) {
  return (
    <div className="flex items-center gap-2">
      <label className="text-xs text-text-faint" htmlFor="goal-consultation-conversation">
        {t('goalConsultation.conversation.switchLabel')}
      </label>
      <select
        id="goal-consultation-conversation"
        className="rounded-md border border-border-strong px-2 py-1 text-sm"
        value={activeConversationId ?? ''}
        disabled={busy || conversations.length === 0}
        onChange={(event) => onSelect(Number(event.target.value))}
      >
        {conversations.map((conversation, index) => (
          <option key={conversation.id} value={conversation.id}>
            {conversationDisplayTitle(conversation.title) ??
              t('goalConsultation.conversation.untitled', { n: index + 1 })}
          </option>
        ))}
      </select>
      <Button type="button" variant="secondary" disabled={busy} onClick={onCreate}>
        {t('goalConsultation.conversation.newButton')}
      </Button>
      <Button
        type="button"
        variant="secondary"
        disabled={busy || activeConversationId === null}
        onClick={onDelete}
      >
        {t('goalConsultation.conversation.deleteButton')}
      </Button>
    </div>
  )
}

export function GoalConsultationTab({ goalId, category }: GoalConsultationTabProps) {
  const aiConfigured = useAiConfigured()
  const [draft, setDraft] = useState('')
  const [history, setHistory] = useState<HistoryEntry[]>([])
  const [selectedAttachmentIds, setSelectedAttachmentIds] = useState<number[]>([])
  const nextId = useRef(0)
  const historyRef = useRef<HTMLDivElement>(null)
  const limits = useGoalConsultationLimits(goalId)
  const conversation = useActiveGoalConsultationConversation(goalId)
  const ask = useAskGoalConsultationQuestion(goalId)
  const activeConversationId = conversation.effectiveConversationId

  // 新しい質問・回答が積まれたら最新を見せる（積み重なると見切れてスクロールが必要になるため）。
  useEffect(() => {
    const container = historyRef.current
    /* v8 ignore next -- 履歴欄は常に描画されるためrefは常にアタッチ済みで、nullには到達しない */
    if (container) container.scrollTop = container.scrollHeight
  }, [history, ask.isPending])

  if (!aiConfigured) {
    return <AiUnconfiguredNotice />
  }

  const maxChars = limits.data?.max_question_chars
  const warning = validationMessage(draft, maxChars)
  const canSend =
    maxChars !== undefined &&
    validateQuestion(draft, maxChars) === null &&
    activeConversationId !== null &&
    !ask.isPending

  function append(entry: (id: number) => HistoryEntry) {
    nextId.current += 1
    const id = nextId.current
    setHistory((current) => [...current, entry(id)])
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!canSend || activeConversationId === null) return
    const text = draft.trim()
    setDraft('')
    append((id) => ({ kind: 'question', id, text }))
    ask.mutate(
      { conversationId: activeConversationId, question: text, attachmentIds: selectedAttachmentIds },
      {
        onSuccess: (answer) => append((id) => ({ kind: 'answer', id, answer })),
        onError: (error) => {
          const code = error instanceof ApiError ? error.code : undefined
          append((id) => ({ kind: 'error', id, messageKey: errorMessageKey(code) }))
        },
      },
    )
  }

  const exampleKeys = questionExampleKeys(category)

  return (
    <div className="flex flex-col gap-4">
      <Card className="flex flex-col gap-3">
        {/* タブボタン自体が見出しの役割を持つため、他のタブと同じく同一内容の見出しは
            タブ内に重複表示しない（MaterialsTab等と同じ方針）。 */}
        <p className="text-xs text-text-faint">{t('goalConsultation.disclaimer')}</p>
        <ConversationSwitcher
          conversations={conversation.conversations}
          activeConversationId={activeConversationId}
          onSelect={(id) => {
            conversation.select(id)
            setHistory([])
            // 会話を切り替えたら添付ファイルの選択はリセットする（他会話への混入を防ぐ、P4）。
            setSelectedAttachmentIds([])
          }}
          onCreate={() => {
            conversation.createNew()
            setHistory([])
            setSelectedAttachmentIds([])
          }}
          onDelete={() => {
            if (!window.confirm(t('goalConsultation.conversation.deleteConfirm'))) return
            conversation.deleteActive()
            setHistory([])
          }}
          busy={conversation.isBusy}
        />
        <ConsultationThread historyRef={historyRef} history={history} pending={ask.isPending} />
        <QuestionInputForm
          onSubmit={handleSubmit}
          exampleKeys={exampleKeys}
          draft={draft}
          setDraft={setDraft}
          warning={warning}
          canSend={canSend}
          pending={ask.isPending}
          selectedAttachmentIds={selectedAttachmentIds}
          setSelectedAttachmentIds={setSelectedAttachmentIds}
        />
      </Card>
      <GoalConsultationHistory goalId={goalId} conversationId={activeConversationId ?? undefined} />
    </div>
  )
}
