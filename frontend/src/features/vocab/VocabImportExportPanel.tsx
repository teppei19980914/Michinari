import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { t } from '../../locales/t'
import { Card } from '../../components/Card'
import { Button } from '../../components/Button'
import { Textarea } from '../../components/Textarea'
import { useToast } from '../../components/toastContext'
import { downloadBlob } from '../../utils/downloadBlob'
import {
  confirmVocabImport,
  exportVocabDeck,
  previewVocabImport,
  type VocabCardType,
  type VocabImportPreview,
  type VocabImportRowRead,
} from '../../api/vocab'
import { QUERY_KEYS } from '../../constants/queryKeys'

//: 一括登録・書き出しの対象（ALLは無い。開発Todo_単語帳_v1.0 要件F F-U8）。
const IMPORT_EXPORT_CARD_TYPES: VocabCardType[] = ['TERM', 'SITUATION']

/** プレビュー結果（件数・エラー・確定ボタン）の表示。親のVocabImportExportPanelが
 * 100行制限に収まるよう分割（CODING_RULES.md「保守性（複雑度）」）。 */
function VocabImportPreviewResult({
  preview,
  onConfirm,
  isConfirming,
}: {
  preview: VocabImportPreview
  onConfirm: () => void
  isConfirming: boolean
}) {
  return (
    <div className="flex flex-col gap-2 rounded-md border border-border p-3">
      <p className="text-sm text-text-secondary">
        {t('vocab.deckDetail.bulkImportSummary', {
          rowCount: preview.rows.length,
          errorCount: preview.errors.length,
          duplicateCount: preview.duplicate_count,
        })}
      </p>
      {preview.errors.length > 0 && (
        <ul className="flex flex-col gap-1 text-xs text-danger-text">
          {preview.errors.map((error) => (
            <li key={error.line_number}>
              {t('vocab.deckDetail.bulkImportErrorRow', {
                line: error.line_number,
                reason: error.reason,
              })}
            </li>
          ))}
        </ul>
      )}
      <div>
        <Button disabled={preview.rows.length === 0 || isConfirming} onClick={onConfirm}>
          {t('vocab.deckDetail.bulkImportConfirmButton')}
        </Button>
      </div>
    </div>
  )
}

/** 種類の選択（TERM/SITUATION、ALLは無い）。一括登録・書き出しの両方で使う
 * （CODING_RULES.md①DRYの原則）。 */
function CardTypeSelect({
  label,
  value,
  onChange,
}: {
  label: string
  value: VocabCardType
  onChange: (value: VocabCardType) => void
}) {
  return (
    <label className="flex flex-col gap-1 text-sm text-text-secondary">
      {label}
      <select
        className="rounded-md border border-border-strong px-3 py-2 text-sm"
        value={value}
        onChange={(e) => onChange(e.target.value as VocabCardType)}
      >
        {IMPORT_EXPORT_CARD_TYPES.map((key) => (
          <option key={key} value={key}>
            {t(`vocab.deckDetail.cardTypeOptions.${key}`)}
          </option>
        ))}
      </select>
    </label>
  )
}

/** 書き出し（種類選択＋ボタン）。親を100行以内に保つための分離。 */
function VocabExportSection({
  deckId,
  deckName,
}: {
  deckId: number
  deckName: string
}) {
  const { showApiError } = useToast()
  const [exportCardType, setExportCardType] = useState<VocabCardType>('TERM')
  const exportMutation = useMutation({
    mutationFn: () => exportVocabDeck(deckId, exportCardType),
    onSuccess: (result) => {
      const blob = new Blob([result.text], { type: 'text/tab-separated-values;charset=utf-8' })
      downloadBlob(blob, `${deckName}.tsv`)
    },
    onError: showApiError,
  })

  return (
    <div className="flex flex-col gap-2">
      <CardTypeSelect
        label={t('vocab.deckDetail.exportCardTypeLabel')}
        value={exportCardType}
        onChange={setExportCardType}
      />
      <div>
        <Button
          variant="secondary"
          disabled={exportMutation.isPending}
          onClick={() => exportMutation.mutate()}
        >
          {t('vocab.deckDetail.exportButton')}
        </Button>
      </div>
    </div>
  )
}

/** 一括登録（貼り付け→プレビュー→確定）と書き出し（タブ区切りテキストのダウンロード）。
 * 種類（用語／シチュエーション、開発Todo_単語帳_v1.0 要件F F-U8）は一括登録・書き出しの
 * それぞれで独立に選べる。 */
export function VocabImportExportPanel({ deckId, deckName }: { deckId: number; deckName: string }) {
  const queryClient = useQueryClient()
  const { showApiError } = useToast()
  const [text, setText] = useState('')
  const [importCardType, setImportCardType] = useState<VocabCardType>('TERM')
  const [preview, setPreview] = useState<VocabImportPreview | null>(null)

  const previewMutation = useMutation({
    mutationFn: () => previewVocabImport(deckId, text, importCardType),
    onSuccess: setPreview,
    onError: showApiError,
  })
  const confirmMutation = useMutation({
    mutationFn: (rows: VocabImportRowRead[]) =>
      confirmVocabImport(
        deckId,
        rows.map((row) => ({
          term: row.term,
          meaning: row.meaning,
          aliases: row.aliases,
          note: row.note,
          situation_text: row.situation_text,
          question_text: row.question_text,
        })),
        importCardType,
      ),
    meta: { overlay: 'saving' },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.vocabCards(deckId) })
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.vocabDeck(deckId) })
      setText('')
      setPreview(null)
    },
    onError: showApiError,
  })
  return (
    <Card className="flex flex-col gap-4">
      <div className="flex flex-col gap-2">
        <h2 className="text-sm font-semibold text-text-primary">
          {t('vocab.deckDetail.bulkImportTitle')}
        </h2>
        <CardTypeSelect
          label={t('vocab.deckDetail.bulkImportCardTypeLabel')}
          value={importCardType}
          onChange={(value) => {
            setImportCardType(value)
            setPreview(null)
          }}
        />
        <Textarea
          value={text}
          onChange={(e) => {
            setText(e.target.value)
            setPreview(null)
          }}
          rows={6}
          placeholder={
            importCardType === 'TERM'
              ? t('vocab.deckDetail.bulkImportPlaceholder')
              : t('vocab.deckDetail.bulkImportPlaceholderSituation')
          }
        />
        <div>
          <Button
            variant="secondary"
            disabled={!text.trim() || previewMutation.isPending}
            onClick={() => previewMutation.mutate()}
          >
            {t('vocab.deckDetail.bulkImportPreviewButton')}
          </Button>
        </div>

        {preview && (
          <VocabImportPreviewResult
            preview={preview}
            onConfirm={() => confirmMutation.mutate(preview.rows)}
            isConfirming={confirmMutation.isPending}
          />
        )}
      </div>

      <VocabExportSection deckId={deckId} deckName={deckName} />
    </Card>
  )
}
