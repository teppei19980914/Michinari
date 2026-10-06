/** ヘルプに質問するドロワー（Phase43、仕様書6.18、開発Todo F-03）。
 *
 * 質問ごとに独立した1往復として送る（文脈は引き継がない、開発Todo U16）。画面に出す履歴は、
 * ドロワーを開いている間だけ保持する。閉じると消える（履歴は端末に保存しない）。 */
import { useRef, useState, type FormEvent } from 'react'
import { ApiError } from '../../api/client'
import type { HelpAssistantAnswer } from '../../api/helpAssistant'
import { Button } from '../../components/Button'
import { Textarea } from '../../components/Textarea'
import { t } from '../../locales/t'
import { errorMessageKey, validateQuestion } from './helpAssistantLogic'
import { HelpAssistantAnswerBody } from './HelpAssistantAnswer'
import { useAskHelpQuestion, useHelpAssistantLimits } from './useHelpAssistant'

/** 画面に積む履歴の1件。質問・回答・エラーのいずれか。 */
type HistoryEntry =
  | { kind: 'question'; id: number; text: string }
  | { kind: 'answer'; id: number; answer: HelpAssistantAnswer }
  | { kind: 'error'; id: number; messageKey: string }

type HelpAssistantDrawerProps = {
  onClose: () => void
}

/** 質問の入力欄の下に出す検証メッセージ（上限が読めるまでは出さない）。 */
function validationMessage(draft: string, maxChars: number | undefined): string | null {
  if (maxChars === undefined) return null
  const error = validateQuestion(draft, maxChars)
  if (error === 'empty') return null
  if (error === 'tooLong') return t('helpAssistant.tooLong', { max: maxChars })
  return null
}

/** 履歴の1件を描画する。 */
function HistoryItem({ entry }: { entry: HistoryEntry }) {
  if (entry.kind === 'question') {
    return (
      <div className="ml-auto max-w-[85%] rounded-md bg-blue-50 p-2 text-sm text-gray-800">
        <p className="mb-1 text-xs text-gray-500">{t('helpAssistant.userLabel')}</p>
        <p className="whitespace-pre-wrap">{entry.text}</p>
      </div>
    )
  }
  return (
    <div className="max-w-[85%] rounded-md bg-gray-50 p-2">
      <p className="mb-1 text-xs text-gray-500">{t('helpAssistant.assistantLabel')}</p>
      {entry.kind === 'answer' ? (
        <HelpAssistantAnswerBody answer={entry.answer} />
      ) : (
        <p className="text-sm text-gray-700">{t(entry.messageKey)}</p>
      )}
    </div>
  )
}

export function HelpAssistantDrawer({ onClose }: HelpAssistantDrawerProps) {
  const [draft, setDraft] = useState('')
  const [history, setHistory] = useState<HistoryEntry[]>([])
  const nextId = useRef(0)
  const limits = useHelpAssistantLimits()
  const ask = useAskHelpQuestion()

  const maxChars = limits.data?.max_question_chars
  const warning = validationMessage(draft, maxChars)
  const canSend = maxChars !== undefined && validateQuestion(draft, maxChars) === null && !ask.isPending

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
    <aside
      role="dialog"
      aria-label={t('helpAssistant.title')}
      className="fixed inset-y-0 right-0 z-40 flex w-full max-w-md flex-col gap-3 border-l border-gray-200 bg-white p-4 shadow-lg"
    >
      <div className="flex items-center justify-between">
        <h2 className="text-base font-semibold text-gray-800">{t('helpAssistant.title')}</h2>
        <Button variant="secondary" onClick={onClose}>
          {t('helpAssistant.close')}
        </Button>
      </div>
      <p className="text-xs text-gray-500">{t('helpAssistant.disclaimer')}</p>
      <div className="flex flex-1 flex-col gap-2 overflow-y-auto">
        {history.map((entry) => (
          <HistoryItem key={entry.id} entry={entry} />
        ))}
        {ask.isPending && <p className="text-sm text-gray-500">{t('helpAssistant.sending')}</p>}
      </div>
      <form onSubmit={handleSubmit} className="flex flex-col gap-2">
        <Textarea
          aria-label={t('helpAssistant.placeholder')}
          placeholder={t('helpAssistant.placeholder')}
          value={draft}
          rows={3}
          disabled={ask.isPending}
          onChange={(event) => setDraft(event.target.value)}
        />
        {warning && <p className="text-xs text-red-600">{warning}</p>}
        <Button type="submit" disabled={!canSend}>
          {t('helpAssistant.send')}
        </Button>
      </form>
    </aside>
  )
}
