/** ナレッジエクスポート（SC-13）の総括レポートの表示。
 *
 * 1関数100行の上限（CODING_RULES.md「保守性（複雑度）」）への対応で KnowledgeExportPage
 * から移したものである。
 *
 * 総括レポート本文は見出しを用いた構造的な文書としてAI生成されるため（GOAL_RETROSPECTIVE /
 * GOAL_RETROSPECTIVE_READINGプロンプト）、WeeklyDigestSectionと同じくMarkdownText
 * （XSS安全設計の詳細もそちらを参照）でプレビュー表示する。 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { t } from '../../locales/t'
import { Card } from '../../components/Card'
import { MarkdownText } from '../../components/MarkdownText'
import { Button } from '../../components/Button'
import { useToast } from '../../components/toastContext'
import { AiUnconfiguredNotice } from '../../components/AiUnconfiguredNotice'
import { useAiConfigured } from '../../hooks/useAiConfigured'
import { generateRetrospective, getRetrospective } from '../../api/closure'
import { QUERY_KEYS } from '../../constants/queryKeys'

export function RetrospectiveSection({
  goalId,
  anonymize,
  isReading,
  canGenerate,
}: {
  goalId: number
  anonymize: boolean
  isReading: boolean
  /** 完了した目標か（canGenerateRetrospective で判定した値を渡す）。 */
  canGenerate: boolean
}) {
  const queryClient = useQueryClient()
  const { showApiError } = useToast()
  const aiConfigured = useAiConfigured()
  const retrospectiveQuery = useQuery({
    queryKey: QUERY_KEYS.retrospectiveView(goalId, anonymize),
    queryFn: () => getRetrospective(goalId, anonymize),
  })

  const mutation = useMutation({
    mutationFn: () => generateRetrospective(goalId, anonymize),
    meta: { overlay: 'saving' },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.retrospective(goalId) })
    },
    onError: showApiError,
  })

  const body = retrospectiveQuery.data?.body ?? null

  return (
    <Card className="flex flex-col gap-2">
      <h2 className="font-medium text-text-primary">
        {t(
          isReading ? 'knowledgeExport.retrospective.readingTitle' : 'knowledgeExport.retrospective.title',
        )}
      </h2>
      {mutation.isPending ? (
        <p className="text-sm text-text-faint">{t('knowledgeExport.retrospective.generating')}</p>
      ) : body ? (
        <MarkdownText text={body} className="text-text-secondary" />
      ) : (
        <p className="text-sm text-text-faint">
          {t(
            isReading ? 'knowledgeExport.retrospective.readingEmpty' : 'knowledgeExport.retrospective.empty',
          )}
        </p>
      )}
      {!canGenerate ? (
        // 完了していない目標では生成しない（利用者方針2026-10-04。既存の本文は閲覧できる）
        <p className="text-sm text-text-faint">
          {t('knowledgeExport.retrospective.requiresCompletedHint')}
        </p>
      ) : aiConfigured ? (
        <div>
          <Button
            variant="secondary"
            disabled={mutation.isPending}
            onClick={() => mutation.mutate()}
          >
            {body
              ? t('knowledgeExport.retrospective.regenerateButton')
              : t('knowledgeExport.retrospective.generateButton')}
          </Button>
        </div>
      ) : (
        <AiUnconfiguredNotice />
      )}
    </Card>
  )
}

/** 仕事目標では、月次報告・半期評価（複数期間分）は既存の総括レポート専用エンドポイント
 * （generateRetrospective/getRetrospective）を使えない（総括レポートは仕事目標を恒久的に
 * 拒否する。データ構造編6.2）。生成・編集は目標詳細画面の月次報告・半期評価タブ
 * （WorkReportTab）で行う設計のため、本画面では案内文のみを表示し、実際の内容は
 * プレビュー・エクスポート結果のMarkdown全文（retrospective選択時）で確認する。 */
export function WorkRetrospectivesNote() {
  return (
    <Card className="flex flex-col gap-2">
      <h2 className="font-medium text-text-primary">
        {t('knowledgeExport.retrospective.workTitle')}
      </h2>
      <p className="text-sm text-text-faint">{t('knowledgeExport.retrospective.workNotice')}</p>
    </Card>
  )
}
