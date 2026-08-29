import { useQuery } from '@tanstack/react-query'
import { t } from '../locales/t'
import { Card } from '../components/Card'
import { apiErrorMessage } from '../api/client'
import { getSystemInfo, type SystemInfoRead } from '../api/systemInfo'

function LibraryTable({ libraries }: { libraries: SystemInfoRead['backend_libraries'] }) {
  return (
    <table className="w-full text-left text-sm">
      <thead>
        <tr className="text-gray-500">
          <th className="py-1 font-medium">{t('systemInfo.libraryNameLabel')}</th>
          <th className="py-1 font-medium">{t('systemInfo.libraryVersionLabel')}</th>
        </tr>
      </thead>
      <tbody>
        {libraries.map((library) => (
          <tr key={library.name} className="border-t border-gray-100">
            <td className="py-1 text-gray-900">{library.name}</td>
            <td className="py-1 text-gray-500">{library.version}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

/** SC-15 システム情報（仕様書6.14）。 */
export function SystemInfoPage() {
  const systemInfoQuery = useQuery({ queryKey: ['systemInfo'], queryFn: getSystemInfo })

  if (systemInfoQuery.isLoading) {
    return <p className="p-6 text-sm text-gray-500">{t('common.loading')}</p>
  }
  if (systemInfoQuery.isError || !systemInfoQuery.data) {
    return <p className="p-6 text-sm text-red-600">{apiErrorMessage(systemInfoQuery.error)}</p>
  }

  const systemInfo = systemInfoQuery.data

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-4 p-4">
      <h1 className="text-xl font-semibold text-gray-900">{t('systemInfo.title')}</h1>

      <Card className="flex flex-col gap-1 text-sm">
        <p>
          <span className="text-gray-500">{t('systemInfo.appVersionLabel')}: </span>
          <span className="text-gray-900">{systemInfo.app_version}</span>
        </p>
        <p>
          <span className="text-gray-500">{t('systemInfo.pythonVersionLabel')}: </span>
          <span className="text-gray-900">{systemInfo.python_version}</span>
        </p>
        <p>
          <span className="text-gray-500">{t('systemInfo.builtAtLabel')}: </span>
          <span className="text-gray-900">
            {systemInfo.built_at
              ? new Date(systemInfo.built_at).toLocaleString()
              : t('systemInfo.builtAtDev')}
          </span>
        </p>
      </Card>

      <Card className="flex flex-col gap-2">
        <h2 className="font-medium text-gray-900">{t('systemInfo.backendLibrariesTitle')}</h2>
        <LibraryTable libraries={systemInfo.backend_libraries} />
      </Card>

      <Card className="flex flex-col gap-2">
        <h2 className="font-medium text-gray-900">{t('systemInfo.frontendLibrariesTitle')}</h2>
        <LibraryTable libraries={systemInfo.frontend_libraries} />
      </Card>
    </div>
  )
}
