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
    bodyKeys: ['help.sections.dashboard.p1', 'help.sections.dashboard.p2'],
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
    ],
  },
  {
    id: 'resources',
    titleKey: 'help.sections.resources.title',
    bodyKeys: ['help.sections.resources.p1', 'help.sections.resources.p2'],
  },
  {
    id: 'calendar',
    titleKey: 'help.sections.calendar.title',
    bodyKeys: ['help.sections.calendar.p1', 'help.sections.calendar.p2'],
  },
  {
    id: 'dailyReport',
    titleKey: 'help.sections.dailyReport.title',
    bodyKeys: [
      'help.sections.dailyReport.p1',
      'help.sections.dailyReport.p2',
      'help.sections.dailyReport.p3',
    ],
  },
  {
    id: 'analytics',
    titleKey: 'help.sections.analytics.title',
    bodyKeys: ['help.sections.analytics.p1'],
  },
  {
    id: 'examAndExport',
    titleKey: 'help.sections.examAndExport.title',
    bodyKeys: ['help.sections.examAndExport.p1', 'help.sections.examAndExport.p2'],
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
