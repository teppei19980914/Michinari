import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { t } from '../../locales/t'
import { Card } from '../../components/Card'
import { Button } from '../../components/Button'
import { useToast } from '../../components/Toast'
import { ApiError } from '../../api/client'
import {
  listPromptTemplates,
  resetPromptTemplate,
  updatePromptTemplate,
  type AiPurpose,
  type PromptTemplateRead,
} from '../../api/settings'

function TemplateEditor({ template }: { template: PromptTemplateRead }) {
  const queryClient = useQueryClient()
  const { showToast } = useToast()
  const [body, setBody] = useState(template.body)

  const handleError = (error: unknown) => {
    showToast(error instanceof ApiError ? error.localizedMessage : t('errors.default'), 'error')
  }
  const invalidate = () => queryClient.invalidateQueries({ queryKey: ['prompt-templates'] })

  const saveMutation = useMutation({
    mutationFn: () => updatePromptTemplate(template.purpose, body),
    onSuccess: () => {
      invalidate()
      showToast(t('common.saveSucceeded'))
    },
    onError: handleError,
  })
  const resetMutation = useMutation({
    mutationFn: () => resetPromptTemplate(template.purpose),
    onSuccess: (reset) => {
      setBody(reset.body)
      invalidate()
    },
    onError: handleError,
  })

  return (
    <div className="rounded-md border border-gray-200 p-3">
      <div className="mb-2 flex items-center justify-between">
        <h3 className="text-sm font-medium text-gray-900">
          {t(`settings.promptTemplate.purpose.${template.purpose}`)}
        </h3>
        {template.is_customized && (
          <span className="rounded bg-blue-50 px-2 py-0.5 text-xs text-blue-700">
            {t('settings.promptTemplate.customizedBadge')}
          </span>
        )}
      </div>
      <textarea
        className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
        rows={6}
        value={body}
        onChange={(e) => setBody(e.target.value)}
      />
      <div className="mt-2 flex justify-end gap-2">
        <Button
          variant="secondary"
          disabled={resetMutation.isPending}
          onClick={() => {
            if (window.confirm(t('settings.promptTemplate.resetConfirm'))) {
              resetMutation.mutate()
            }
          }}
        >
          {t('common.action.reset')}
        </Button>
        <Button disabled={saveMutation.isPending} onClick={() => saveMutation.mutate()}>
          {t('common.action.save')}
        </Button>
      </div>
    </div>
  )
}

/** プロンプトテンプレート編集（仕様書6.11。Phase7完了条件「プロンプトテンプレートが編集でき、
 * 初期値に戻せる」）。 */
export function PromptTemplateSection() {
  const query = useQuery({ queryKey: ['prompt-templates'], queryFn: listPromptTemplates })

  return (
    <Card className="flex flex-col gap-3">
      <h2 className="font-medium text-gray-900">{t('settings.promptTemplate.title')}</h2>
      {query.data?.map((template: PromptTemplateRead) => (
        <TemplateEditor key={template.purpose as AiPurpose} template={template} />
      ))}
    </Card>
  )
}
