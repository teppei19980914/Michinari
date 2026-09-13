/** 月次報告・半期評価（WorkReportTab.tsx）のレビュー用フォームの値を保持するフック。
 *
 * 1関数100行の上限（CODING_RULES.md「保守性（複雑度）」）への対応で、入力値の`useState`と
 * 「取得・生成・保存の結果をフォームへ反映する」処理だけを切り出したものである。
 *
 * このフックは WorkReportTab の直下で呼ぶこと。フォーム（WorkReportForm）は報告が
 * 未取得のあいだ描画されないため、条件付きで描画される側へフックを移すと、生成のたびに
 * 入力内容が失われて振る舞いが変わる。 */
import { useEffect, useState } from 'react'
import type { WorkReportRead } from '../../api/closure'

export interface WorkReportDraft {
  businessSummary: string
  setBusinessSummary: (value: string) => void
  targetGoalText: string
  setTargetGoalText: (value: string) => void
  achievementScore: number | null
  setAchievementScore: (value: number | null) => void
  achievementReflection: string
  setAchievementReflection: (value: string) => void
  nextGoalText: string
  setNextGoalText: (value: string) => void
  reportNotes: string
  setReportNotes: (value: string) => void
  /** 生成・保存の結果をフォームへ反映する。 */
  applyReport: (report: WorkReportRead) => void
}

/** `report` は取得前が`undefined`、該当期間の報告が未生成なら`null`になる（api/closure.ts）。
 * どちらの場合もフォームへは何も反映しない。 */
export function useWorkReportDraft(report: WorkReportRead | null | undefined): WorkReportDraft {
  const [businessSummary, setBusinessSummary] = useState('')
  const [targetGoalText, setTargetGoalText] = useState('')
  const [achievementScore, setAchievementScore] = useState<number | null>(null)
  const [achievementReflection, setAchievementReflection] = useState('')
  const [nextGoalText, setNextGoalText] = useState('')
  const [reportNotes, setReportNotes] = useState('')

  const applyReport = (loaded: WorkReportRead) => {
    setBusinessSummary(loaded.business_summary ?? '')
    setTargetGoalText(loaded.target_goal_text ?? '')
    setAchievementScore(loaded.achievement_score)
    setAchievementReflection(loaded.achievement_reflection ?? '')
    setNextGoalText(loaded.next_goal_text ?? '')
    setReportNotes(loaded.report_notes ?? '')
  }

  useEffect(() => {
    if (report) {
      applyReport(report)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [report])

  return {
    businessSummary,
    setBusinessSummary,
    targetGoalText,
    setTargetGoalText,
    achievementScore,
    setAchievementScore,
    achievementReflection,
    setAchievementReflection,
    nextGoalText,
    setNextGoalText,
    reportNotes,
    setReportNotes,
    applyReport,
  }
}
