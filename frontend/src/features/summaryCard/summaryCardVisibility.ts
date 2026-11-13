/** カードの項目ごとの表示・非表示（画面状態のみ、保存しない。仕様書6.10「プレビュー」）。 */
export const SUMMARY_CARD_ITEM_KEYS = [
  'recordDays',
  'longestConsecutiveDays',
  'topTheme',
  'milestones',
  'roadmap',
  'aiSentence',
] as const

export type SummaryCardItemKey = (typeof SUMMARY_CARD_ITEM_KEYS)[number]

export type SummaryCardVisibility = Record<SummaryCardItemKey, boolean>

/** 既定は全項目表示（利用者が個別に非表示へ切り替える、仕様書6.10）。 */
export function createDefaultVisibility(): SummaryCardVisibility {
  return {
    recordDays: true,
    longestConsecutiveDays: true,
    topTheme: true,
    milestones: true,
    roadmap: true,
    aiSentence: true,
  }
}

export function toggleVisibility(
  current: SummaryCardVisibility,
  key: SummaryCardItemKey,
  visible: boolean,
): SummaryCardVisibility {
  return { ...current, [key]: visible }
}
