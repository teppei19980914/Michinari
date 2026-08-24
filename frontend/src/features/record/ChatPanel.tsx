import { useState } from 'react'
import { t } from '../../locales/t'
import { Button } from '../../components/Button'
import { Textarea } from '../../components/Textarea'
import type { components } from '../../types/api.d.ts'

type ChatMessageRead = components['schemas']['ChatMessageRead']

type ChatPanelProps = {
  messages: ChatMessageRead[]
  /** 直近のAI呼び出しで縮退が発生したか（仕様書6.5「縮退の発生が対話領域に通知される」）。 */
  wasTruncated?: boolean
  readOnly?: boolean
  onSend?: (message: string) => void
  isSending?: boolean
}

/** AI対話領域（SC-06下段の対話、SC-08の対話履歴表示を共有、仕様書6.5・6.7）。 */
export function ChatPanel({
  messages,
  wasTruncated = false,
  readOnly = false,
  onSend,
  isSending = false,
}: ChatPanelProps) {
  const [draft, setDraft] = useState('')

  return (
    <div className="flex flex-col gap-2">
      {messages.length === 0 ? (
        <p className="text-sm text-gray-500">{t('dailyReport.chat.empty')}</p>
      ) : (
        <ul className="flex flex-col gap-2">
          {messages.map((message) => (
            <li
              key={message.id}
              className={`max-w-[85%] rounded-lg px-3 py-2 text-sm ${
                message.role === 'USER'
                  ? 'ml-auto bg-blue-600 text-white'
                  : 'bg-gray-100 text-gray-900'
              }`}
            >
              <p className="whitespace-pre-wrap">{message.content}</p>
            </li>
          ))}
        </ul>
      )}

      {wasTruncated && (
        <p className="text-xs text-amber-700">{t('dailyReport.chat.truncatedNotice')}</p>
      )}

      {!readOnly && onSend && (
        <div className="flex gap-2">
          <Textarea
            rows={2}
            className="flex-1"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder={t('dailyReport.chat.inputPlaceholder')}
          />
          <Button
            type="button"
            disabled={isSending || draft.trim() === ''}
            onClick={() => {
              onSend(draft)
              setDraft('')
            }}
          >
            {t('dailyReport.chat.sendButton')}
          </Button>
        </div>
      )}
    </div>
  )
}
