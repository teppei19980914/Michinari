/** ヘルプ画面（SC-14）の内容構成。文言は全てlocaleキー経由（frontend/src/locales/ja.json
 * の`help`名前空間）で解決し、ここでは構造とキー名のみを保持する（CODING_RULES.md
 * ゼロハードコーディング）。プロンプトのプレースホルダー名（`{{today}}`等）はAIへ送る
 * テンプレート構文そのもの（backend/app/ai/prompt_builder.pyの変数名と一致させる一次情報源
 * が設計書 ロジック・プロンプト編17章）であり、UI文言ではないためlocale化の対象外とする。
 */

export type HelpSection = {
  id: string
  titleKey: string
  bodyKeys: string[]
}

export const HELP_SECTIONS: HelpSection[] = [
  {
    id: 'intro',
    titleKey: 'help.sections.intro.title',
    bodyKeys: ['help.sections.intro.p1', 'help.sections.intro.p2', 'help.sections.intro.p3'],
  },
  {
    id: 'dashboard',
    titleKey: 'help.sections.dashboard.title',
    bodyKeys: [
      'help.sections.dashboard.p1',
      'help.sections.dashboard.p2',
      'help.sections.dashboard.p3',
      'help.sections.dashboard.p4',
    ],
  },
  {
    id: 'goals',
    titleKey: 'help.sections.goals.title',
    bodyKeys: [
      'help.sections.goals.p1',
      'help.sections.goals.p2',
      'help.sections.goals.p3',
      'help.sections.goals.p4',
      'help.sections.goals.p5',
      'help.sections.goals.p6',
    ],
  },
  {
    id: 'bookshelf',
    titleKey: 'help.sections.bookshelf.title',
    bodyKeys: ['help.sections.bookshelf.p1', 'help.sections.bookshelf.p2'],
  },
  {
    id: 'resources',
    titleKey: 'help.sections.resources.title',
    bodyKeys: ['help.sections.resources.p1', 'help.sections.resources.p2'],
  },
  {
    id: 'calendar',
    titleKey: 'help.sections.calendar.title',
    bodyKeys: [
      'help.sections.calendar.p1',
      'help.sections.calendar.p2',
      'help.sections.calendar.p3',
    ],
  },
  {
    id: 'dailyReport',
    titleKey: 'help.sections.dailyReport.title',
    bodyKeys: [
      'help.sections.dailyReport.p1',
      'help.sections.dailyReport.p2',
      'help.sections.dailyReport.p3',
      'help.sections.dailyReport.p4',
      'help.sections.dailyReport.p5',
    ],
  },
  {
    id: 'analytics',
    titleKey: 'help.sections.analytics.title',
    bodyKeys: [
      'help.sections.analytics.p1',
      'help.sections.analytics.p2',
      'help.sections.analytics.p3',
    ],
  },
  {
    id: 'examAndExport',
    titleKey: 'help.sections.examAndExport.title',
    bodyKeys: [
      'help.sections.examAndExport.p1',
      'help.sections.examAndExport.p2',
      'help.sections.examAndExport.p3',
    ],
  },
  {
    id: 'aiConnection',
    titleKey: 'help.sections.aiConnection.title',
    bodyKeys: [
      'help.sections.aiConnection.p1',
      'help.sections.aiConnection.p2',
      'help.sections.aiConnection.p3',
    ],
  },
  {
    id: 'settingsOther',
    titleKey: 'help.sections.settingsOther.title',
    bodyKeys: [
      'help.sections.settingsOther.p1',
      'help.sections.settingsOther.p2',
      'help.sections.settingsOther.p3',
      'help.sections.settingsOther.p4',
      'help.sections.settingsOther.p5',
      'help.sections.settingsOther.p6',
    ],
  },
  {
    id: 'desktop',
    titleKey: 'help.sections.desktop.title',
    bodyKeys: [
      'help.sections.desktop.p1',
      'help.sections.desktop.p2',
      'help.sections.desktop.p3',
      'help.sections.desktop.p4',
      'help.sections.desktop.p5',
    ],
  },
  {
    id: 'promptVariables',
    titleKey: 'help.sections.promptVariables.title',
    bodyKeys: ['help.sections.promptVariables.p1'],
  },
  {
    id: 'dataManagement',
    titleKey: 'help.sections.dataManagement.title',
    bodyKeys: ['help.sections.dataManagement.p1'],
  },
  {
    id: 'faq',
    titleKey: 'help.sections.faq.title',
    bodyKeys: [],
  },
]

export type HelpFaqItem = {
  questionKey: string
  answerKey: string
}

export const HELP_FAQ_ITEMS: HelpFaqItem[] = [
  { questionKey: 'help.sections.faq.q1', answerKey: 'help.sections.faq.a1' },
  { questionKey: 'help.sections.faq.q2', answerKey: 'help.sections.faq.a2' },
  { questionKey: 'help.sections.faq.q3', answerKey: 'help.sections.faq.a3' },
  { questionKey: 'help.sections.faq.q4', answerKey: 'help.sections.faq.a4' },
  { questionKey: 'help.sections.faq.q5', answerKey: 'help.sections.faq.a5' },
  { questionKey: 'help.sections.faq.q6', answerKey: 'help.sections.faq.a6' },
]

export type HelpPromptVariable = {
  /** プロンプトテンプレート中に記述する`{{変数名}}`の変数名部分（コード上の識別子のため非翻訳）。 */
  name: string
  descriptionKey: string
}

export type HelpPromptPurpose = {
  id: string
  titleKey: string
  variables: HelpPromptVariable[]
}

/** 設計書 ロジック・プロンプト編17章の変数表と一致させる（一次情報源）。 */
export const HELP_PROMPT_PURPOSES: HelpPromptPurpose[] = [
  {
    id: 'dailyFeedback',
    titleKey: 'help.sections.promptVariables.purposes.dailyFeedback.title',
    variables: [
      { name: 'today', descriptionKey: 'help.sections.promptVariables.purposes.dailyFeedback.variables.today' },
      { name: 'day_type', descriptionKey: 'help.sections.promptVariables.purposes.dailyFeedback.variables.day_type' },
      {
        name: 'load_coefficient',
        descriptionKey: 'help.sections.promptVariables.purposes.dailyFeedback.variables.load_coefficient',
      },
      {
        name: 'goal_summary',
        descriptionKey: 'help.sections.promptVariables.purposes.dailyFeedback.variables.goal_summary',
      },
      {
        name: 'material_status',
        descriptionKey: 'help.sections.promptVariables.purposes.dailyFeedback.variables.material_status',
      },
      {
        name: 'slot_summary',
        descriptionKey: 'help.sections.promptVariables.purposes.dailyFeedback.variables.slot_summary',
      },
      {
        name: 'buffer_usage_rate',
        descriptionKey: 'help.sections.promptVariables.purposes.dailyFeedback.variables.buffer_usage_rate',
      },
      {
        name: 'today_logs',
        descriptionKey: 'help.sections.promptVariables.purposes.dailyFeedback.variables.today_logs',
      },
      {
        name: 'diary_body',
        descriptionKey: 'help.sections.promptVariables.purposes.dailyFeedback.variables.diary_body',
      },
      {
        name: 'diary_learned',
        descriptionKey: 'help.sections.promptVariables.purposes.dailyFeedback.variables.diary_learned',
      },
      {
        name: 'weekly_summaries',
        descriptionKey: 'help.sections.promptVariables.purposes.dailyFeedback.variables.weekly_summaries',
      },
      {
        name: 'conversation_history',
        descriptionKey: 'help.sections.promptVariables.purposes.dailyFeedback.variables.conversation_history',
      },
      {
        name: 'perspective_suggestion',
        descriptionKey: 'help.sections.promptVariables.purposes.dailyFeedback.variables.perspective_suggestion',
      },
    ],
  },
  {
    id: 'weeklySummary',
    titleKey: 'help.sections.promptVariables.purposes.weeklySummary.title',
    variables: [
      { name: 'week_range', descriptionKey: 'help.sections.promptVariables.purposes.weeklySummary.variables.week_range' },
      { name: 'goal_name', descriptionKey: 'help.sections.promptVariables.purposes.weeklySummary.variables.goal_name' },
      { name: 'week_logs', descriptionKey: 'help.sections.promptVariables.purposes.weeklySummary.variables.week_logs' },
      {
        name: 'week_diaries',
        descriptionKey: 'help.sections.promptVariables.purposes.weeklySummary.variables.week_diaries',
      },
      {
        name: 'week_metrics',
        descriptionKey: 'help.sections.promptVariables.purposes.weeklySummary.variables.week_metrics',
      },
      { name: 'anonymize', descriptionKey: 'help.sections.promptVariables.purposes.weeklySummary.variables.anonymize' },
    ],
  },
  {
    id: 'dailyMessage',
    titleKey: 'help.sections.promptVariables.purposes.dailyMessage.title',
    variables: [
      { name: 'today', descriptionKey: 'help.sections.promptVariables.purposes.dailyMessage.variables.today' },
      { name: 'day_type', descriptionKey: 'help.sections.promptVariables.purposes.dailyMessage.variables.day_type' },
      {
        name: 'goal_summary',
        descriptionKey: 'help.sections.promptVariables.purposes.dailyMessage.variables.goal_summary',
      },
      {
        name: 'progress_summary',
        descriptionKey: 'help.sections.promptVariables.purposes.dailyMessage.variables.progress_summary',
      },
      {
        name: 'recent_activity',
        descriptionKey: 'help.sections.promptVariables.purposes.dailyMessage.variables.recent_activity',
      },
    ],
  },
  {
    id: 'goalRetrospective',
    titleKey: 'help.sections.promptVariables.purposes.goalRetrospective.title',
    variables: [
      {
        name: 'goal_summary',
        descriptionKey: 'help.sections.promptVariables.purposes.goalRetrospective.variables.goal_summary',
      },
      {
        name: 'material_summary',
        descriptionKey: 'help.sections.promptVariables.purposes.goalRetrospective.variables.material_summary',
      },
      {
        name: 'overall_metrics',
        descriptionKey: 'help.sections.promptVariables.purposes.goalRetrospective.variables.overall_metrics',
      },
      {
        name: 'quality_trend',
        descriptionKey: 'help.sections.promptVariables.purposes.goalRetrospective.variables.quality_trend',
      },
      {
        name: 'replan_history',
        descriptionKey: 'help.sections.promptVariables.purposes.goalRetrospective.variables.replan_history',
      },
      {
        name: 'weekly_summaries',
        descriptionKey: 'help.sections.promptVariables.purposes.goalRetrospective.variables.weekly_summaries',
      },
      {
        name: 'exam_results',
        descriptionKey: 'help.sections.promptVariables.purposes.goalRetrospective.variables.exam_results',
      },
      {
        name: 'anonymize',
        descriptionKey: 'help.sections.promptVariables.purposes.goalRetrospective.variables.anonymize',
      },
    ],
  },
  {
    id: 'dailyFeedbackReading',
    titleKey: 'help.sections.promptVariables.purposes.dailyFeedbackReading.title',
    variables: [
      { name: 'today', descriptionKey: 'help.sections.promptVariables.purposes.dailyFeedbackReading.variables.today' },
      {
        name: 'book_summary',
        descriptionKey: 'help.sections.promptVariables.purposes.dailyFeedbackReading.variables.book_summary',
      },
      {
        name: 'today_recall',
        descriptionKey: 'help.sections.promptVariables.purposes.dailyFeedbackReading.variables.today_recall',
      },
      {
        name: 'recent_recalls',
        descriptionKey: 'help.sections.promptVariables.purposes.dailyFeedbackReading.variables.recent_recalls',
      },
      {
        name: 'perspective_suggestion',
        descriptionKey: 'help.sections.promptVariables.purposes.dailyFeedbackReading.variables.perspective_suggestion',
      },
    ],
  },
  {
    id: 'dailyFeedbackWork',
    titleKey: 'help.sections.promptVariables.purposes.dailyFeedbackWork.title',
    variables: [
      { name: 'today', descriptionKey: 'help.sections.promptVariables.purposes.dailyFeedbackWork.variables.today' },
      {
        name: 'work_summary',
        descriptionKey: 'help.sections.promptVariables.purposes.dailyFeedbackWork.variables.work_summary',
      },
      {
        name: 'today_work',
        descriptionKey: 'help.sections.promptVariables.purposes.dailyFeedbackWork.variables.today_work',
      },
      {
        name: 'recent_work_logs',
        descriptionKey: 'help.sections.promptVariables.purposes.dailyFeedbackWork.variables.recent_work_logs',
      },
      {
        name: 'perspective_suggestion',
        descriptionKey: 'help.sections.promptVariables.purposes.dailyFeedbackWork.variables.perspective_suggestion',
      },
    ],
  },
  {
    id: 'weeklySummaryReadingWork',
    titleKey: 'help.sections.promptVariables.purposes.weeklySummaryReadingWork.title',
    variables: [
      {
        name: 'week_range',
        descriptionKey: 'help.sections.promptVariables.purposes.weeklySummaryReadingWork.variables.week_range',
      },
      {
        name: 'book_title',
        descriptionKey: 'help.sections.promptVariables.purposes.weeklySummaryReadingWork.variables.book_title',
      },
      {
        name: 'week_recalls',
        descriptionKey: 'help.sections.promptVariables.purposes.weeklySummaryReadingWork.variables.week_recalls',
      },
      {
        name: 'work_name',
        descriptionKey: 'help.sections.promptVariables.purposes.weeklySummaryReadingWork.variables.work_name',
      },
      {
        name: 'week_logs',
        descriptionKey: 'help.sections.promptVariables.purposes.weeklySummaryReadingWork.variables.week_logs',
      },
      {
        name: 'anonymize',
        descriptionKey: 'help.sections.promptVariables.purposes.weeklySummaryReadingWork.variables.anonymize',
      },
    ],
  },
  {
    id: 'goalRetrospectiveReading',
    titleKey: 'help.sections.promptVariables.purposes.goalRetrospectiveReading.title',
    variables: [
      {
        name: 'book_summary',
        descriptionKey: 'help.sections.promptVariables.purposes.goalRetrospectiveReading.variables.book_summary',
      },
      {
        name: 'overall_metrics',
        descriptionKey: 'help.sections.promptVariables.purposes.goalRetrospectiveReading.variables.overall_metrics',
      },
      {
        name: 'weekly_summaries',
        descriptionKey: 'help.sections.promptVariables.purposes.goalRetrospectiveReading.variables.weekly_summaries',
      },
      {
        name: 'reading_logs',
        descriptionKey: 'help.sections.promptVariables.purposes.goalRetrospectiveReading.variables.reading_logs',
      },
      {
        name: 'anonymize',
        descriptionKey: 'help.sections.promptVariables.purposes.goalRetrospectiveReading.variables.anonymize',
      },
    ],
  },
  {
    id: 'goalRetrospectiveWork',
    titleKey: 'help.sections.promptVariables.purposes.goalRetrospectiveWork.title',
    variables: [
      {
        name: 'work_summary',
        descriptionKey: 'help.sections.promptVariables.purposes.goalRetrospectiveWork.variables.work_summary',
      },
      {
        name: 'target_month_or_period',
        descriptionKey:
          'help.sections.promptVariables.purposes.goalRetrospectiveWork.variables.target_month_or_period',
      },
      {
        name: 'target_goal_text',
        descriptionKey: 'help.sections.promptVariables.purposes.goalRetrospectiveWork.variables.target_goal_text',
      },
      {
        name: 'weekly_summaries',
        descriptionKey: 'help.sections.promptVariables.purposes.goalRetrospectiveWork.variables.weekly_summaries',
      },
      {
        name: 'month_or_period_logs',
        descriptionKey:
          'help.sections.promptVariables.purposes.goalRetrospectiveWork.variables.month_or_period_logs',
      },
      {
        name: 'anonymize',
        descriptionKey: 'help.sections.promptVariables.purposes.goalRetrospectiveWork.variables.anonymize',
      },
    ],
  },
  {
    id: 'evaluationReportWork',
    titleKey: 'help.sections.promptVariables.purposes.evaluationReportWork.title',
    variables: [
      {
        name: 'member_summary',
        descriptionKey: 'help.sections.promptVariables.purposes.evaluationReportWork.variables.member_summary',
      },
      {
        name: 'considerations',
        descriptionKey: 'help.sections.promptVariables.purposes.evaluationReportWork.variables.considerations',
      },
      {
        name: 'feedback_history',
        descriptionKey: 'help.sections.promptVariables.purposes.evaluationReportWork.variables.feedback_history',
      },
      {
        name: 'work_logs',
        descriptionKey: 'help.sections.promptVariables.purposes.evaluationReportWork.variables.work_logs',
      },
    ],
  },
  {
    id: 'recapThemes',
    titleKey: 'help.sections.promptVariables.purposes.recapThemes.title',
    variables: [
      {
        name: 'existing_themes',
        descriptionKey: 'help.sections.promptVariables.purposes.recapThemes.variables.existing_themes',
      },
      {
        name: 'entries',
        descriptionKey: 'help.sections.promptVariables.purposes.recapThemes.variables.entries',
      },
      {
        name: 'theme_name',
        descriptionKey: 'help.sections.promptVariables.purposes.recapThemes.variables.theme_name',
      },
      {
        name: 'current_body',
        descriptionKey: 'help.sections.promptVariables.purposes.recapThemes.variables.current_body',
      },
      {
        name: 'new_entries',
        descriptionKey: 'help.sections.promptVariables.purposes.recapThemes.variables.new_entries',
      },
      {
        name: 'body_max_chars',
        descriptionKey: 'help.sections.promptVariables.purposes.recapThemes.variables.body_max_chars',
      },
    ],
  },
  {
    id: 'helpAssistant',
    titleKey: 'help.sections.promptVariables.purposes.helpAssistant.title',
    variables: [
      {
        name: 'help_body',
        descriptionKey: 'help.sections.promptVariables.purposes.helpAssistant.variables.help_body',
      },
      {
        name: 'question',
        descriptionKey: 'help.sections.promptVariables.purposes.helpAssistant.variables.question',
      },
      {
        name: 'nonce',
        descriptionKey: 'help.sections.promptVariables.purposes.helpAssistant.variables.nonce',
      },
    ],
  },
]

export type HelpSearchEntry = {
  id: string
  title: string
  body: string[]
}

/**
 * ヘルプ画面のキーワード検索（純粋関数）。呼び出し側で`t()`により翻訳解決済みの
 * タイトル・本文を渡す（ロケールに依存させずテスト可能にするため）。
 * 大文字小文字を区別せず、タイトルまたは本文いずれかへの部分一致でセクションIDを返す。
 * クエリが空（前後空白のみを含む）の場合は全件のIDを返す。
 */
export function filterHelpSections(entries: HelpSearchEntry[], query: string): string[] {
  const normalized = query.trim().toLowerCase()
  if (!normalized) {
    return entries.map((entry) => entry.id)
  }
  return entries
    .filter(
      (entry) =>
        entry.title.toLowerCase().includes(normalized) ||
        entry.body.some((paragraph) => paragraph.toLowerCase().includes(normalized)),
    )
    .map((entry) => entry.id)
}
