/**
 * 1年前の今日（開発Todo_1年前の今日_v1.0）の設定（SC-11）の入力判定。
 *
 * CODING_RULES.md「フロントの分岐は `.ts` へ切り出す」に従い、判定を純粋関数として
 * ここに置き、コンポーネント（OnThisDaySection.tsx）は描画と通信に専念させる。
 */

import type { AppSettingsUpdate } from '../../api/settings'
import { isValidThresholdList } from './milestoneThresholdSettings'

export type OnThisDaySettingsGuard = {
  canSubmit: boolean
  errorKey: string | null
}

export type OnThisDaySettingsDraft = {
  enabled: boolean
  candidateMonthsAgo: string
  showProbability: number
  bodyPreviewChars: number
}

/** 候補（カンマ区切りの正の整数、何か月前か）が保存できる形式かを判定する。バックエンドの
 * `settings_service._parse_threshold_list`と同じ検証（milestone thresholdと共有）。 */
export function isValidCandidateMonthsAgo(value: string): boolean {
  return isValidThresholdList(value)
}

export function resolveOnThisDaySettingsGuard(
  draft: OnThisDaySettingsDraft,
): OnThisDaySettingsGuard {
  if (!isValidCandidateMonthsAgo(draft.candidateMonthsAgo)) {
    return { canSubmit: false, errorKey: 'settings.onThisDay.candidateMonthsAgoInvalid' }
  }
  if (draft.showProbability < 0 || draft.showProbability > 1) {
    return { canSubmit: false, errorKey: 'settings.onThisDay.showProbabilityInvalid' }
  }
  if (!Number.isInteger(draft.bodyPreviewChars) || draft.bodyPreviewChars < 1) {
    return { canSubmit: false, errorKey: 'settings.onThisDay.bodyPreviewCharsInvalid' }
  }
  return { canSubmit: true, errorKey: null }
}

export function buildOnThisDaySettingsPayload(
  draft: OnThisDaySettingsDraft,
): NonNullable<AppSettingsUpdate['on_this_day']> {
  return {
    enabled: draft.enabled,
    candidate_months_ago: draft.candidateMonthsAgo,
    show_probability: draft.showProbability,
    body_preview_chars: draft.bodyPreviewChars,
  }
}
