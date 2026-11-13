import { useRef, useState, type RefObject } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { t } from '../../locales/t'
import { Card } from '../../components/Card'
import { Input } from '../../components/Input'
import { Button } from '../../components/Button'
import { useToast } from '../../components/toastContext'
import { AiUnconfiguredNotice } from '../../components/AiUnconfiguredNotice'
import { useAiConfigured } from '../../hooks/useAiConfigured'
import { apiErrorMessage } from '../../api/client'
import { getToday } from '../../api/records'
import type { GoalCategory } from '../../api/goals'
import { generateSummaryCardSentence, getSummaryCard } from '../../api/summaryCard'
import { downloadBlob } from '../../utils/downloadBlob'
import { QUERY_KEYS } from '../../constants/queryKeys'
import { SummaryCardPreview } from './SummaryCardPreview'
import { defaultOpenPeriod, type SummaryCardPeriod } from './summaryCardPeriod'
import {
  copyPngBlobToClipboard,
  isClipboardImageCopySupported,
  svgElementToPngBlob,
} from './summaryCardImage'
import {
  createDefaultVisibility,
  SUMMARY_CARD_ITEM_KEYS,
  toggleVisibility,
  type SummaryCardItemKey,
} from './summaryCardVisibility'

export type SummaryCardSectionProps = {
  goalId: number
  goalName: string
  category: GoalCategory
} & (
  | { mode: 'open' }
  | { mode: 'fixed'; fixedPeriod: SummaryCardPeriod }
)

function PeriodControls({
  period,
  logicalDate,
  onChange,
}: {
  period: SummaryCardPeriod
  logicalDate: string
  onChange: (period: SummaryCardPeriod) => void
}) {
  return (
    <div className="flex flex-wrap items-end gap-2">
      <Button
        variant="secondary"
        onClick={() => onChange(defaultOpenPeriod(logicalDate))}
      >
        {t('summaryCard.periodPresetThisYear')}
      </Button>
      <label className="flex flex-col gap-1 text-sm text-text-secondary">
        {t('summaryCard.periodFromLabel')}
        <Input
          type="date"
          value={period.dateFrom}
          max={period.dateTo}
          onChange={(e) => onChange({ ...period, dateFrom: e.target.value })}
        />
      </label>
      <label className="flex flex-col gap-1 text-sm text-text-secondary">
        {t('summaryCard.periodToLabel')}
        <Input
          type="date"
          value={period.dateTo}
          min={period.dateFrom}
          onChange={(e) => onChange({ ...period, dateTo: e.target.value })}
        />
      </label>
    </div>
  )
}

function VisibilityToggles({
  visibility,
  onToggle,
}: {
  visibility: ReturnType<typeof createDefaultVisibility>
  onToggle: (key: SummaryCardItemKey, visible: boolean) => void
}) {
  return (
    <div className="flex flex-col gap-1">
      <h3 className="text-sm font-medium text-text-secondary">
        {t('summaryCard.visibilityTitle')}
      </h3>
      <div className="grid grid-cols-2 gap-1">
        {SUMMARY_CARD_ITEM_KEYS.map((key) => (
          <label key={key} className="flex items-center gap-2 text-sm text-text-secondary">
            <input
              type="checkbox"
              checked={visibility[key]}
              onChange={(e) => onToggle(key, e.target.checked)}
            />
            {t(`summaryCard.labels.${key}`)}
          </label>
        ))}
      </div>
    </div>
  )
}

function SummaryCardActions({
  aiConfigured,
  onGenerateSentence,
  isGeneratingSentence,
  onSave,
  isSaving,
  onCopy,
  isCopying,
}: {
  aiConfigured: boolean
  onGenerateSentence: () => void
  isGeneratingSentence: boolean
  onSave: () => void
  isSaving: boolean
  onCopy: () => void
  isCopying: boolean
}) {
  const copySupported = isClipboardImageCopySupported()
  return (
    <>
      {aiConfigured ? (
        <Button variant="secondary" disabled={isGeneratingSentence} onClick={onGenerateSentence}>
          {t('summaryCard.generateSentenceButton')}
        </Button>
      ) : (
        <AiUnconfiguredNotice />
      )}
      <div className="flex flex-wrap gap-2">
        <Button disabled={isSaving} onClick={onSave}>
          {t('summaryCard.saveButton')}
        </Button>
        <Button variant="secondary" disabled={isCopying || !copySupported} onClick={onCopy}>
          {t('summaryCard.copyButton')}
        </Button>
      </div>
      {!copySupported && (
        <p className="text-xs text-text-faint">{t('summaryCard.copyUnsupportedNote')}</p>
      )}
    </>
  )
}

/** AI一文の生成・PNG保存・クリップボードコピーの3操作をまとめる（1関数100行の上限、
 * CODING_RULES.md「保守性（複雑度）」への対応でSummaryCardSectionから切り出した）。 */
function useSummaryCardActions(params: {
  goalId: number
  period: SummaryCardPeriod | null
  previewRef: RefObject<SVGSVGElement | null>
  onSentence: (sentence: string) => void
}) {
  const { goalId, period, previewRef, onSentence } = params
  const { showToast, showApiError } = useToast()

  const sentenceMutation = useMutation({
    mutationFn: () => generateSummaryCardSentence(goalId, period!.dateFrom, period!.dateTo),
    onSuccess: (data) => onSentence(data.sentence),
    onError: showApiError,
  })
  const saveMutation = useMutation({
    mutationFn: async () => {
      const svg = previewRef.current
      // 保存ボタンはプレビュー（SummaryCardPreview）と同じreturn分岐で描画されるため、
      // ボタンがDOMに存在する時点でrefは必ず設定済み（到達しない防御的分岐、
      // OPERATIONS.md「到達不能な防御的分岐」）。
      /* v8 ignore next 2 */
      if (!svg || !period) return
      const blob = await svgElementToPngBlob(svg)
      downloadBlob(blob, `michinari-summary-card_${period.dateFrom}_${period.dateTo}.png`)
    },
    onSuccess: () => showToast(t('summaryCard.saveSucceeded')),
    onError: showApiError,
  })
  const copyMutation = useMutation({
    mutationFn: async () => {
      const svg = previewRef.current
      // コピーボタンも同じ理由で到達しない防御的分岐（上記saveMutationと同じ）。
      /* v8 ignore next */
      if (!svg) return
      const blob = await svgElementToPngBlob(svg)
      await copyPngBlobToClipboard(blob)
    },
    onSuccess: () => showToast(t('summaryCard.copySucceeded')),
    onError: showApiError,
  })
  return { sentenceMutation, saveMutation, copyMutation }
}

/** ふりかえりまとめ・共有カード（仕様書6.2 SC-03・6.10 SC-13、開発Todo「まとめと共有カード」
 * v1.0）。期間指定モード（目標詳細の基本情報タブ、`mode: 'open'`）と目標完了時モード
 * （ナレッジエクスポート画面、`mode: 'fixed'`）の両方から同じコンポーネントを使う
 * （カード内容・プレビュー・PNG保存・コピー操作は共通、仕様書6.2）。 */
export function SummaryCardSection(props: SummaryCardSectionProps) {
  const { goalId, goalName, category, mode } = props
  const aiConfigured = useAiConfigured()
  const previewRef = useRef<SVGSVGElement>(null)

  const todayQuery = useQuery({
    queryKey: QUERY_KEYS.today(),
    queryFn: getToday,
    enabled: mode === 'open',
  })
  const [openPeriod, setOpenPeriod] = useState<SummaryCardPeriod | null>(null)
  const [visibility, setVisibility] = useState(createDefaultVisibility())
  const [sentence, setSentence] = useState<string | null>(null)

  const period =
    mode === 'fixed'
      ? props.fixedPeriod
      : openPeriod ?? (todayQuery.data ? defaultOpenPeriod(todayQuery.data.logical_date) : null)

  const summaryQuery = useQuery({
    queryKey: period ? QUERY_KEYS.summaryCard(goalId, period.dateFrom, period.dateTo) : [],
    queryFn: () => getSummaryCard(goalId, period!.dateFrom, period!.dateTo),
    enabled: period !== null,
  })

  const { sentenceMutation, saveMutation, copyMutation } = useSummaryCardActions({
    goalId,
    period,
    previewRef,
    onSentence: setSentence,
  })

  if ((mode === 'open' && todayQuery.isLoading) || !period || summaryQuery.isLoading) {
    return (
      <Card>
        <p className="text-sm text-text-faint">{t('common.loading')}</p>
      </Card>
    )
  }
  if (summaryQuery.isError || !summaryQuery.data) {
    return (
      <Card>
        <p className="text-sm text-danger-text">{apiErrorMessage(summaryQuery.error)}</p>
      </Card>
    )
  }
  const aggregate = summaryQuery.data

  return (
    <Card className="flex flex-col gap-3">
      <h2 className="font-medium text-text-primary">{t('summaryCard.title')}</h2>

      {mode === 'open' && todayQuery.data ? (
        <PeriodControls
          period={period}
          logicalDate={todayQuery.data.logical_date}
          onChange={setOpenPeriod}
        />
      ) : (
        <p className="text-sm text-text-faint">{t('summaryCard.fixedPeriodNote')}</p>
      )}

      <div className="overflow-auto">
        <SummaryCardPreview
          ref={previewRef}
          goalName={goalName}
          category={category}
          period={period}
          aggregate={aggregate}
          visibility={visibility}
          sentence={sentence}
        />
      </div>

      <VisibilityToggles
        visibility={visibility}
        onToggle={(key, visible) => setVisibility((current) => toggleVisibility(current, key, visible))}
      />

      <SummaryCardActions
        aiConfigured={aiConfigured}
        onGenerateSentence={() => sentenceMutation.mutate()}
        isGeneratingSentence={sentenceMutation.isPending}
        onSave={() => saveMutation.mutate()}
        isSaving={saveMutation.isPending}
        onCopy={() => copyMutation.mutate()}
        isCopying={copyMutation.isPending}
      />
    </Card>
  )
}
