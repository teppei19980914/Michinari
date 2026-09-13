import type { ReactNode } from 'react'
import { Card } from '../../components/Card'
import { Button } from '../../components/Button'
import { ChatPanel } from './ChatPanel'
import type { ChatMessageRead } from '../../api/records'
import type { CategoryChat } from './useCategoryChat'
import type { CategoryFinalize } from './useCategoryFinalize'
import { t } from '../../locales/t'

export type CategoryReportLabels = {
  /** 実績入力セクションの見出し。 */
  title: string
  /** AI対話セクションの見出し。 */
  chatTitle: string
  /** 対話開始ボタンの文言（実績を送信してフィードバックを受け取る）。 */
  chatStartLabel: string
  /** 確定ボタンの文言。 */
  finalizeLabel: string
}

export type CategoryReportSectionProps = {
  labels: CategoryReportLabels
  /** このカテゴリが確定済みか。確定済みなら入力欄・確定ボタンを出さず読み取り専用にする。 */
  isReported: boolean
  /** 確定済みのときに表示する実績のサマリ。 */
  summary: ReactNode
  /** 未確定のときに表示する入力欄。 */
  editor: ReactNode
  /** このカテゴリの対話履歴（purposeと対象目標で絞り込み済み）。 */
  messages: ChatMessageRead[]
  chat: CategoryChat
  finalize: CategoryFinalize
}

/**
 * 日次報告の1カテゴリ分（実績入力/サマリ・AI対話・確定ボタン）の構成。
 *
 * 資格試験・読書・仕事の3カテゴリは、確定済みかどうかによる出し分け、対話の開始/送信の
 * 出し分け、確定ボタンの出し分けがすべて同一で、異なるのは文言と中身の入力欄・サマリだけで
 * ある。従来は同じ構造が3回書かれており、確定まわりの仕様変更のたびに3箇所へ同じ修正を
 * 入れる必要があった（CODING_RULES.md「①DRYの原則」）。
 *
 * 確定はカテゴリごとに独立しているため、このコンポーネントは他カテゴリの状態を一切参照
 * しない（仕様変更2026-09-05、仕様書1.1（改20））。
 *
 * 実績入力セクションとAI対話カードと確定ボタンは、呼び出し側の縦並び（gap）にそのまま
 * 並ぶ必要があるため、まとめる要素を挟まずフラグメントで返す。
 */
export function CategoryReportSection({
  labels,
  isReported,
  summary,
  editor,
  messages,
  chat,
  finalize,
}: CategoryReportSectionProps) {
  return (
    <>
      {isReported ? (
        <section className="flex flex-col gap-3">
          <h2 className="font-medium text-gray-900">
            {labels.title}
            <span className="ml-2 text-xs font-normal text-gray-400">
              {t('dailyReport.confirmedBadge')}
            </span>
          </h2>
          {summary}
        </section>
      ) : (
        <section className="flex flex-col gap-3">
          <h2 className="font-medium text-gray-900">{labels.title}</h2>
          {editor}
        </section>
      )}

      <Card className="flex flex-col gap-3">
        <h2 className="font-medium text-gray-900">{labels.chatTitle}</h2>
        {isReported ? (
          <ChatPanel messages={messages} readOnly />
        ) : (
          <>
            {messages.length === 0 && (
              <Button disabled={chat.isPending} onClick={() => chat.send(null)}>
                {labels.chatStartLabel}
              </Button>
            )}
            <ChatPanel
              messages={messages}
              wasTruncated={chat.wasTruncated}
              isSending={chat.isPending}
              onSend={messages.length > 0 ? (message) => chat.send(message) : undefined}
            />
          </>
        )}
      </Card>

      {!isReported && (
        <div className="flex justify-end">
          <Button disabled={finalize.isPending} onClick={() => finalize.submit()}>
            {labels.finalizeLabel}
          </Button>
        </div>
      )}
    </>
  )
}
