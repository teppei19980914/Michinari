/** 日次報告閲覧のセクション表示と対話履歴の振り分けを固定する（Phase 36）。
 *
 * 用途（purpose）と目標の組み合わせを取り違えても、画面には何かが表示されるため
 * 見ただけでは気づけない。どの履歴にどのメッセージが入るかをここで押さえる。
 *
 * 表示可否の規則そのものは sectionVisibility.test.ts が担うため、ここでは
 * 「その規則へ何を中身として渡しているか」に絞る。 */
import { describe, expect, it } from 'vitest'
import type { ChatMessageRead } from '../../api/records'
import type { GoalRead } from '../../api/goals'
import { resolveDailyReportViewSections } from './dailyReportViewSections'

const EXAM_GOAL = { id: 1, category: 'EXAM' } as GoalRead
const READING_GOAL = { id: 2, category: 'READING' } as GoalRead

function message(
  id: number,
  purpose: ChatMessageRead['purpose'],
  goalId: number | null,
): ChatMessageRead {
  return {
    id,
    sequence: id,
    role: 'ASSISTANT',
    purpose,
    goal_id: goalId,
    content: `content-${id}`,
    created_at: '2026-09-13T12:00:00',
  }
}

const EXAM_MESSAGE = message(1, 'DAILY_FEEDBACK', EXAM_GOAL.id)
const READING_MESSAGE = message(2, 'DAILY_FEEDBACK_READING', READING_GOAL.id)
const WORK_MESSAGE = message(3, 'DAILY_FEEDBACK_WORK', 3)
/** 目標単位の会話へ分離する前に記録された、goal_idを持たないメッセージ。 */
const LEGACY_MESSAGE = message(4, 'DAILY_FEEDBACK', null)
/** 別の資格試験目標宛て。選択していない間は出してはいけない。 */
const OTHER_GOAL_MESSAGE = message(5, 'DAILY_FEEDBACK', 99)
/** 日次フィードバック以外の用途。どの履歴にも入れてはいけない。 */
const WEEKLY_MESSAGE = message(6, 'WEEKLY_SUMMARY', EXAM_GOAL.id)

const ALL_MESSAGES = [
  EXAM_MESSAGE,
  READING_MESSAGE,
  WORK_MESSAGE,
  LEGACY_MESSAGE,
  OTHER_GOAL_MESSAGE,
  WEEKLY_MESSAGE,
]

function resolve({
  chatMessages = ALL_MESSAGES,
  readingLogs = [] as unknown[],
  workLogs = [] as unknown[],
  diaryEntries = [] as never[],
  showGoalSelector = false,
  selectedGoal = undefined as GoalRead | undefined,
} = {}) {
  return resolveDailyReportViewSections({
    record: { chat_messages: chatMessages, reading_logs: readingLogs, work_logs: workLogs },
    diaryEntries,
    goalTabs: { showGoalSelector, selectedGoal },
  })
}

describe('resolveDailyReportViewSections', () => {
  it('always shows the exam section even on a day with no record', () => {
    // 実績も日記も無い日でも「報告済みだが記録なし」として開ける従来の挙動。
    const sections = resolve({ chatMessages: [] })
    expect(sections.showExamSection).toBe(true)
    expect(sections.showReadingSection).toBe(false)
    expect(sections.showWorkSection).toBe(false)
    expect(sections.showDiarySection).toBe(false)
  })

  it('shows the reading and work sections once they have a log', () => {
    const sections = resolve({ readingLogs: [{}], workLogs: [{}] })
    expect(sections.showReadingSection).toBe(true)
    expect(sections.showWorkSection).toBe(true)
  })

  it('shows the diary section once an entry is written', () => {
    expect(resolve({ diaryEntries: [{}] as never[] }).showDiarySection).toBe(true)
  })

  it('files each feedback message under the history of its own purpose', () => {
    const sections = resolve()
    expect(sections.chatHistories.map((history) => history.key)).toEqual([
      'exam',
      'reading',
      'work',
    ])
    const exam = sections.chatHistories[0]
    expect(exam.messages.map((m) => m.id)).toEqual([
      EXAM_MESSAGE.id,
      LEGACY_MESSAGE.id,
      OTHER_GOAL_MESSAGE.id,
    ])
    expect(sections.chatHistories[1].messages.map((m) => m.id)).toEqual([READING_MESSAGE.id])
    expect(sections.chatHistories[2].messages.map((m) => m.id)).toEqual([WORK_MESSAGE.id])
  })

  it('excludes the purposes that are not daily feedback', () => {
    const everyMessageId = resolve().chatHistories.flatMap((history) =>
      history.messages.map((m) => m.id),
    )
    expect(everyMessageId).not.toContain(WEEKLY_MESSAGE.id)
  })

  it('narrows to the selected goal but keeps the messages with no goal', () => {
    const sections = resolve({ showGoalSelector: true, selectedGoal: EXAM_GOAL })
    expect(sections.chatHistories.map((history) => history.key)).toEqual(['exam'])
    expect(sections.chatHistories[0].messages.map((m) => m.id)).toEqual([
      EXAM_MESSAGE.id,
      LEGACY_MESSAGE.id,
    ])
  })

  it('shows only the history of the selected category while the tabs are visible', () => {
    const sections = resolve({ showGoalSelector: true, selectedGoal: READING_GOAL })
    expect(sections.chatHistories.map((history) => history.key)).toEqual(['reading'])
  })

  it('drops a history that has no message left after the filtering', () => {
    // 選択中の目標宛ての資格試験メッセージが1件も無いなら、見出しごと出さない。
    const sections = resolve({
      chatMessages: [OTHER_GOAL_MESSAGE],
      showGoalSelector: true,
      selectedGoal: EXAM_GOAL,
    })
    expect(sections.chatHistories).toEqual([])
  })

  it('gives each history a distinct heading', () => {
    const titleKeys = resolve().chatHistories.map((history) => history.titleKey)
    expect(new Set(titleKeys).size).toBe(titleKeys.length)
  })
})
