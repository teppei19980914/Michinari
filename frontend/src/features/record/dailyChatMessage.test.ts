import { describe, expect, it } from 'vitest'
import type { ChatMessageRead } from '../../api/records'
import { appendChatExchange, filterCategoryMessages } from './dailyChatMessage'

const ASSISTANT_MESSAGE: ChatMessageRead = {
  id: 100,
  goal_id: 1,
  purpose: 'DAILY_FEEDBACK',
  role: 'ASSISTANT',
  content: 'assistant',
  sequence: 1,
  created_at: '2026-09-13T00:00:00Z',
}

const EXISTING_MESSAGE: ChatMessageRead = { ...ASSISTANT_MESSAGE, id: 99, sequence: 0 }

describe('appendChatExchange', () => {
  it('appends both the user message and the assistant reply', () => {
    const result = appendChatExchange([EXISTING_MESSAGE], {
      goalId: 1,
      purpose: 'DAILY_FEEDBACK',
      message: 'hello',
      assistantMessage: ASSISTANT_MESSAGE,
    })

    expect(result).toHaveLength(3)
    expect(result[0]).toBe(EXISTING_MESSAGE)
    expect(result[1]).toMatchObject({
      goal_id: 1,
      purpose: 'DAILY_FEEDBACK',
      role: 'USER',
      content: 'hello',
      sequence: 1,
    })
    expect(result[2]).toBe(ASSISTANT_MESSAGE)
  })

  it('gives the locally added user message a negative id so it cannot collide with server ids', () => {
    const result = appendChatExchange([], {
      goalId: 2,
      purpose: 'DAILY_FEEDBACK_READING',
      message: 'hello',
      assistantMessage: ASSISTANT_MESSAGE,
    })

    expect(result[0].id).toBeLessThan(0)
  })

  it('appends only the assistant reply when there is no user message', () => {
    // 初回の「実績を送信してAIフィードバックを受け取る」はメッセージなしで送信する。
    const result = appendChatExchange([EXISTING_MESSAGE], {
      goalId: 3,
      purpose: 'DAILY_FEEDBACK_WORK',
      message: null,
      assistantMessage: ASSISTANT_MESSAGE,
    })

    expect(result).toEqual([EXISTING_MESSAGE, ASSISTANT_MESSAGE])
  })

  it('keeps the given history untouched', () => {
    const current = [EXISTING_MESSAGE]
    appendChatExchange(current, {
      goalId: 1,
      purpose: 'DAILY_FEEDBACK',
      message: 'hello',
      assistantMessage: ASSISTANT_MESSAGE,
    })
    expect(current).toEqual([EXISTING_MESSAGE])
  })
})

describe('filterCategoryMessages', () => {
  const examMessage: ChatMessageRead = { ...ASSISTANT_MESSAGE, id: 1, goal_id: 1 }
  const otherGoalExamMessage: ChatMessageRead = { ...ASSISTANT_MESSAGE, id: 2, goal_id: 9 }
  const readingMessage: ChatMessageRead = {
    ...ASSISTANT_MESSAGE,
    id: 3,
    goal_id: 1,
    purpose: 'DAILY_FEEDBACK_READING',
  }
  const legacyMessage: ChatMessageRead = { ...ASSISTANT_MESSAGE, id: 4, goal_id: null }
  const all = [examMessage, otherGoalExamMessage, readingMessage, legacyMessage]

  it('keeps only the messages of the given purpose and goal', () => {
    expect(filterCategoryMessages(all, 'DAILY_FEEDBACK', 1)).toEqual([examMessage, legacyMessage])
  })

  it('separates the categories that share the same chat_messages array', () => {
    expect(filterCategoryMessages(all, 'DAILY_FEEDBACK_READING', 1)).toEqual([readingMessage])
  })

  it('keeps messages saved before the per-goal split (goal_id is null)', () => {
    expect(filterCategoryMessages(all, 'DAILY_FEEDBACK', 9)).toEqual([
      otherGoalExamMessage,
      legacyMessage,
    ])
  })
})

describe('appendChatExchange with an empty message', () => {
  it('does not add a user entry for an empty string', () => {
    // 空文字の送信はChatPanelが抑止しているが、切り出し前の判定（truthy）を保つ。
    const result = appendChatExchange([], {
      goalId: 1,
      purpose: 'DAILY_FEEDBACK',
      message: '',
      assistantMessage: ASSISTANT_MESSAGE,
    })
    expect(result).toEqual([ASSISTANT_MESSAGE])
  })
})
