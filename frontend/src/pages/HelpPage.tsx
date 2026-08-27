import { useMemo, useState } from 'react'
import { t } from '../locales/t'
import { Card } from '../components/Card'
import { Input } from '../components/Input'
import {
  HELP_FAQ_ITEMS,
  HELP_PROMPT_PURPOSES,
  HELP_SECTIONS,
  filterHelpSections,
  type HelpSearchEntry,
} from '../features/help/helpContent'

function buildSearchEntries(): HelpSearchEntry[] {
  return HELP_SECTIONS.map((section) => {
    const body = section.bodyKeys.map((key) => t(key))
    if (section.id === 'faq') {
      for (const item of HELP_FAQ_ITEMS) {
        body.push(t(item.questionKey), t(item.answerKey))
      }
    }
    if (section.id === 'promptVariables') {
      for (const purpose of HELP_PROMPT_PURPOSES) {
        body.push(t(purpose.titleKey))
        for (const variable of purpose.variables) {
          body.push(variable.name, t(variable.descriptionKey))
        }
      }
    }
    return { id: section.id, title: t(section.titleKey), body }
  })
}

/** SC-14 ヘルプ。アプリの使い方を集約する画面（ユーザー要望：ヘルプ画面への一元集約、
 * 網羅性重視）。内容は完全に静的な参照情報のため、バックエンドAPIは呼び出さない。 */
export function HelpPage() {
  const [query, setQuery] = useState('')
  const searchEntries = useMemo(buildSearchEntries, [])
  const visibleIds = useMemo(() => new Set(filterHelpSections(searchEntries, query)), [searchEntries, query])

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-4 p-4">
      <h1 className="text-xl font-semibold text-gray-900">{t('help.title')}</h1>
      <p className="text-sm text-gray-600">{t('help.subtitle')}</p>

      <Card className="flex flex-col gap-2">
        <label className="flex flex-col gap-1 text-sm text-gray-700">
          {t('help.searchLabel')}
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={t('help.searchPlaceholder')}
          />
        </label>
      </Card>

      <Card className="flex flex-col gap-1">
        <h2 className="font-medium text-gray-900">{t('help.tocTitle')}</h2>
        <ul className="grid grid-cols-1 gap-1 text-sm text-blue-600 sm:grid-cols-2">
          {HELP_SECTIONS.filter((section) => visibleIds.has(section.id)).map((section) => (
            <li key={section.id}>
              <a href={`#${section.id}`} className="hover:underline">
                {t(section.titleKey)}
              </a>
            </li>
          ))}
        </ul>
      </Card>

      {visibleIds.size === 0 && (
        <p className="text-sm text-gray-500">{t('help.searchNoResults')}</p>
      )}

      {HELP_SECTIONS.filter((section) => visibleIds.has(section.id)).map((section) => (
        <Card key={section.id} id={section.id} className="flex flex-col gap-2">
          <h2 className="font-medium text-gray-900">{t(section.titleKey)}</h2>
          {section.bodyKeys.map((key) => (
            <p key={key} className="text-sm text-gray-700">
              {t(key)}
            </p>
          ))}

          {section.id === 'promptVariables' &&
            HELP_PROMPT_PURPOSES.map((purpose) => (
              <div key={purpose.id} className="mt-2">
                <h3 className="text-sm font-medium text-gray-900">{t(purpose.titleKey)}</h3>
                <div className="mt-1 overflow-x-auto">
                  <table className="w-full text-left text-xs text-gray-700">
                    <tbody>
                      {purpose.variables.map((variable) => (
                        <tr key={variable.name} className="border-b border-gray-100 last:border-0">
                          <td className="whitespace-nowrap py-1 pr-3 font-mono text-gray-900">
                            {`{{${variable.name}}}`}
                          </td>
                          <td className="py-1 text-gray-700">{t(variable.descriptionKey)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            ))}

          {section.id === 'faq' && (
            <dl className="flex flex-col gap-3">
              {HELP_FAQ_ITEMS.map((item) => (
                <div key={item.questionKey}>
                  <dt className="text-sm font-medium text-gray-900">{t(item.questionKey)}</dt>
                  <dd className="text-sm text-gray-700">{t(item.answerKey)}</dd>
                </div>
              ))}
            </dl>
          )}
        </Card>
      ))}
    </div>
  )
}
