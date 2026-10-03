/** AI接続設定（仕様書6.11）の、用途ごとのアシスタント設定項目の一覧。
 *
 * コンポーネントと同じファイルに置くと Fast Refresh が効かなくなるため
 * （oxlint react/only-export-components）、値と型だけをこのファイルへ分ける。
 *
 * 用途と設定項目の対応が崩れても画面には同じ形の選択欄が並ぶだけで気づけないため、
 * 一覧はこの1箇所に集約する。 */
import type { AppSettingsRead } from '../../api/settings'

type AiConnection = AppSettingsRead['ai_connection']

export const ASSISTANT_FIELDS = [
  {
    field: 'assistant_uid_daily_feedback',
    labelKey: 'settings.aiConnection.assistant.dailyFeedback',
  },
  {
    field: 'assistant_uid_daily_feedback_reading',
    labelKey: 'settings.aiConnection.assistant.dailyFeedbackReading',
  },
  {
    field: 'assistant_uid_daily_feedback_work',
    labelKey: 'settings.aiConnection.assistant.dailyFeedbackWork',
  },
  {
    field: 'assistant_uid_weekly_summary',
    labelKey: 'settings.aiConnection.assistant.weeklySummary',
  },
  {
    field: 'assistant_uid_weekly_summary_reading',
    labelKey: 'settings.aiConnection.assistant.weeklySummaryReading',
  },
  {
    field: 'assistant_uid_weekly_summary_work',
    labelKey: 'settings.aiConnection.assistant.weeklySummaryWork',
  },
  { field: 'assistant_uid_daily_message', labelKey: 'settings.aiConnection.assistant.dailyMessage' },
  {
    field: 'assistant_uid_goal_retrospective',
    labelKey: 'settings.aiConnection.assistant.goalRetrospective',
  },
  {
    field: 'assistant_uid_goal_retrospective_reading',
    labelKey: 'settings.aiConnection.assistant.goalRetrospectiveReading',
  },
  {
    field: 'assistant_uid_goal_retrospective_work_monthly',
    labelKey: 'settings.aiConnection.assistant.goalRetrospectiveWorkMonthly',
  },
  {
    field: 'assistant_uid_goal_retrospective_work_semiannual',
    labelKey: 'settings.aiConnection.assistant.goalRetrospectiveWorkSemiannual',
  },
  {
    field: 'assistant_uid_evaluation_report_work',
    labelKey: 'settings.aiConnection.assistant.evaluationReportWork',
  },
] as const

export type AssistantUidField = Extract<keyof AiConnection, `assistant_uid_${string}`>
type DeclaredAssistantField = (typeof ASSISTANT_FIELDS)[number]['field']

// assistant_uid_*設定項目を画面に追加し忘れる回帰（読書用の2項目が長期間UI未対応だった実例）を
// tscのビルドエラーとして検出するための網羅性チェック。型が一致しない場合はコンパイルが失敗する。
type _AssistantFieldsAreExhaustive = [AssistantUidField] extends [DeclaredAssistantField]
  ? [DeclaredAssistantField] extends [AssistantUidField]
    ? true
    : never
  : never
const _assistantFieldsAreExhaustive: _AssistantFieldsAreExhaustive = true
void _assistantFieldsAreExhaustive
