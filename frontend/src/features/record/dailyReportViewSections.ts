/** 日次報告閲覧（SC-08 DailyReportViewPage）で、どのセクションを出すかと、AI対話履歴を
 * どの見出しへ振り分けるかを決める。
 *
 * 用途（purpose）と目標の組み合わせで振り分け先が変わるため、取り違えても画面には
 * 「何かが表示されている」状態になり、見ただけでは気づけない。判定を画面から切り離して
 * 単体テストで固定する（OPERATIONS.md「フロントエンドのテストとカバレッジ」）。
 *
 * セクションの表示可否そのものは日次報告（SC-06）と同じ規則（sectionVisibility.ts）へ
 * 委ねる。ここはその規則へ渡す「中身の有無」を組み立てる役割に徹する。 */
import type { ChatMessageRead } from '../../api/records'
import type { components } from '../../types/api.d.ts'
import { isSectionVisible, type GoalTabState } from './sectionVisibility'

type DiaryEntryRead = components['schemas']['DiaryEntryRead']

/** 1つの見出しにまとめて表示する対話履歴。 */
export interface ChatHistorySection {
  /** Reactのkey兼、どのカテゴリの履歴かの識別子。 */
  key: 'exam' | 'reading' | 'work'
  /** 見出しの文言（ロケールキー）。 */
  titleKey: string
  messages: ChatMessageRead[]
}

export interface DailyReportViewSections {
  showExamSection: boolean
  showReadingSection: boolean
  showWorkSection: boolean
  showDiarySection: boolean
  /** 表示する対話履歴だけを、画面に並べる順で返す。 */
  chatHistories: ChatHistorySection[]
}

/** カテゴリごとの用途と見出しの対応。順序がそのまま画面の並び順になる。 */
const CHAT_HISTORY_DEFINITIONS: {
  key: ChatHistorySection['key']
  category: 'EXAM' | 'READING' | 'WORK'
  purpose: string
  titleKey: string
}[] = [
  {
    key: 'exam',
    category: 'EXAM',
    purpose: 'DAILY_FEEDBACK',
    titleKey: 'dailyReportView.chatHistory.title',
  },
  {
    key: 'reading',
    category: 'READING',
    purpose: 'DAILY_FEEDBACK_READING',
    titleKey: 'dailyReportView.readingChatHistory.title',
  },
  {
    key: 'work',
    category: 'WORK',
    purpose: 'DAILY_FEEDBACK_WORK',
    titleKey: 'dailyReportView.workChatHistory.title',
  },
]

/**
 * 表示するセクションと対話履歴を決める。
 *
 * 日次フィードバックを目標単位の会話へ分離したため（Phase26、未決事項L-07の解消方針
 * 転換）、目標タブ表示中（着手中の目標が2件以上）は選択中の目標宛て（＋goal_id=nullの
 * 移行前レガシー）のみに絞り込む。タブが無い場合は従来どおりカテゴリ（purpose）のみでの
 * 絞り込みとする（1目標のみ、または閲覧時点で全目標がクローズ済みでも、その日の記録を
 * 漏れなく表示するため）。
 *
 * @param record その日の記録（対話・実績）
 * @param diaryEntries 本文または学んだことが書かれている日記のみ（filterWrittenDiaryEntries済み）
 * @param goalTabs 目標タブの状態
 */
export function resolveDailyReportViewSections({
  record,
  diaryEntries,
  goalTabs,
}: {
  record: {
    chat_messages: ChatMessageRead[]
    reading_logs: unknown[]
    work_logs: unknown[]
  }
  diaryEntries: DiaryEntryRead[]
  goalTabs: GoalTabState
}): DailyReportViewSections {
  const matchesSelectedGoal = (message: ChatMessageRead) =>
    !goalTabs.showGoalSelector ||
    message.goal_id === goalTabs.selectedGoal?.id ||
    message.goal_id === null

  const chatHistories = CHAT_HISTORY_DEFINITIONS.map((definition) => ({
    key: definition.key,
    titleKey: definition.titleKey,
    category: definition.category,
    messages: record.chat_messages.filter(
      (message) => message.purpose === definition.purpose && matchesSelectedGoal(message),
    ),
  }))
    .filter((history) => isSectionVisible(goalTabs, history.category, history.messages.length > 0))
    .map(({ key, titleKey, messages }) => ({ key, titleKey, messages }))

  return {
    // 資格試験のみ中身の有無を問わない。実績も日記も無い日でも、その日を「報告済みだが
    // 記録なし」として開けるようにするための従来の挙動。
    showExamSection: isSectionVisible(goalTabs, 'EXAM', true),
    showReadingSection: isSectionVisible(goalTabs, 'READING', record.reading_logs.length > 0),
    showWorkSection: isSectionVisible(goalTabs, 'WORK', record.work_logs.length > 0),
    showDiarySection: isSectionVisible(goalTabs, 'EXAM', diaryEntries.length > 0),
    chatHistories,
  }
}
