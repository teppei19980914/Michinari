/** 目標相談チャットのタブ（S09、要件定義書R-104）。
 *
 * 資格目標の詳細画面に常設する（ヘルプの全画面浮動ボタンとは別系統、開発Todo U2）。
 * 質問ごとに独立した1往復として送る（文脈は引き継がない、開発Todo U8）。画面に出す履歴は、
 * タブを表示している間だけ保持する（他のタブへ切り替えて戻ると消える。履歴の永続化はS10）。 */
import { useEffect, useRef, useState, type FormEvent } from 'react'
import { ApiError } from '../../api/client'
import type { GoalConsultationAnswer } from '../../api/goalConsultation'
import { AiUnconfiguredNotice } from '../../components/AiUnconfiguredNotice'
import { Button } from '../../components/Button'
import { Card } from '../../components/Card'
import { Textarea } from '../../components/Textarea'
import { useAiConfigured } from '../../hooks/useAiConfigured'
import { t } from '../../locales/t'
import { errorMessageKey, validateQuestion } from './goalConsultationLogic'
import { GoalConsultationAnswerBody } from './GoalConsultationAnswer'
import { useAskGoalConsultationQuestion, useGoalConsultationLimits } from './useGoalConsultation'

/** 画面に積む履歴の1件。質問・回答・エラーのいずれか。 */
type HistoryEntry =
  | { kind: 'question'; id: number; text: string }
  | { kind: 'answer'; id: number; answer: GoalConsultationAnswer }
  | { kind: 'error'; id: number; messageKey: string }

type GoalConsultationTabProps = {
  goalId: number
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

export function GoalConsultationTab({ goalId }: GoalConsultationTabProps) {
  const aiConfigured = useAiConfigured()
  const [draft, setDraft] = useState('')
  const [history, setHistory] = useState<HistoryEntry[]>([])
  const nextId = useRef(0)
  const historyRef = useRef<HTMLDivElement>(null)
  const limits = useGoalConsultationLimits(goalId)
  const ask = useAskGoalConsultationQuestion(goalId)

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
    maxChars !== undefined && validateQuestion(draft, maxChars) === null && !ask.isPending

  function append(entry: (id: number) => HistoryEntry) {
    nextId.current += 1
    const id = nextId.current
    setHistory((current) => [...current, entry(id)])
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!canSend) return
    const text = draft.trim()
    setDraft('')
    append((id) => ({ kind: 'question', id, text }))
    ask.mutate(text, {
      onSuccess: (answer) => append((id) => ({ kind: 'answer', id, answer })),
      onError: (error) => {
        const code = error instanceof ApiError ? error.code : undefined
        append((id) => ({ kind: 'error', id, messageKey: errorMessageKey(code) }))
      },
    })
  }

  return (
    <Card className="flex flex-col gap-3">
      {/* タブボタン自体が見出しの役割を持つため、他のタブと同じく同一内容の見出しは
          タブ内に重複表示しない（MaterialsTab等と同じ方針）。 */}
      <p className="text-xs text-text-faint">{t('goalConsultation.disclaimer')}</p>
      <div ref={historyRef} className="flex max-h-96 flex-col gap-2 overflow-y-auto">
        {history.length === 0 && (
          <p className="text-sm text-text-faint">{t('goalConsultation.noHistoryYet')}</p>
        )}
        {history.map((entry) => (
          <HistoryItem key={entry.id} entry={entry} />
        ))}
        {ask.isPending && (
          <p className="text-sm text-text-faint">{t('goalConsultation.sending')}</p>
        )}
      </div>
      <form onSubmit={handleSubmit} className="flex flex-col gap-2">
        <Textarea
          aria-label={t('goalConsultation.placeholder')}
          placeholder={t('goalConsultation.placeholder')}
          value={draft}
          rows={3}
          disabled={ask.isPending}
          onChange={(event) => setDraft(event.target.value)}
        />
        {warning && <p className="text-xs text-danger-text">{warning}</p>}
        <Button type="submit" disabled={!canSend}>
          {t('goalConsultation.send')}
        </Button>
      </form>
    </Card>
  )
}
