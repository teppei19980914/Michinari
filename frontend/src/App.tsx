import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Outlet, Route, createBrowserRouter, createRoutesFromElements, RouterProvider } from 'react-router-dom'
import { ROUTE_PATTERNS } from './constants/routes'
import { ToastProvider } from './components/Toast'
import { GlobalNav } from './components/GlobalNav'
import { DashboardPage } from './pages/DashboardPage'
import { GoalsListPage } from './pages/GoalsListPage'
import { GoalDetailPage } from './pages/GoalDetailPage'
import { ExamResultPage } from './pages/ExamResultPage'
import { KnowledgeExportPage } from './pages/KnowledgeExportPage'
import { ResourceSettingsPage } from './pages/ResourceSettingsPage'
import { SettingsPage } from './pages/SettingsPage'
import { DataManagementPage } from './pages/DataManagementPage'
import { SystemInfoPage } from './pages/SystemInfoPage'
import { CalendarPage } from './pages/CalendarPage'
import { DailyReportPage } from './pages/DailyReportPage'
import { ProgressOnlyPage } from './pages/ProgressOnlyPage'
import { DailyReportViewPage } from './pages/DailyReportViewPage'
import { AnalyticsPage } from './pages/AnalyticsPage'
import { HelpPage } from './pages/HelpPage'

const queryClient = new QueryClient()

/** 全画面共通のレイアウト（グローバルナビゲーション）。data router化（createBrowserRouter）
 * したのは、SC-06の「確定前に画面を離脱した場合の警告」をアプリ内遷移（GlobalNavのリンク
 * クリック等）にも適用するため、react-router-domの`useBlocker`を使う必要があるから
 * （`useBlocker`はdata routerでのみ動作し、`<BrowserRouter>`+`<Routes>`の宣言的構成では
 * 使用できない）。ページ側の実装は features/record/useUnsavedChangesWarning.ts と
 * DailyReportPage.tsx を参照。 */
function Layout() {
  return (
    <>
      <GlobalNav />
      <Outlet />
    </>
  )
}

const router = createBrowserRouter(
  createRoutesFromElements(
    <Route element={<Layout />}>
      <Route path={ROUTE_PATTERNS.dashboard} element={<DashboardPage />} />
      <Route path={ROUTE_PATTERNS.goals} element={<GoalsListPage />} />
      <Route path={ROUTE_PATTERNS.goalDetail} element={<GoalDetailPage />} />
      <Route path={ROUTE_PATTERNS.goalExport} element={<KnowledgeExportPage />} />
      <Route path={ROUTE_PATTERNS.goalResult} element={<ExamResultPage />} />
      <Route path={ROUTE_PATTERNS.resources} element={<ResourceSettingsPage />} />
      <Route path={ROUTE_PATTERNS.calendar} element={<CalendarPage />} />
      <Route path={ROUTE_PATTERNS.analytics} element={<AnalyticsPage />} />
      <Route path={ROUTE_PATTERNS.settings} element={<SettingsPage />} />
      <Route path={ROUTE_PATTERNS.settingsData} element={<DataManagementPage />} />
      <Route path={ROUTE_PATTERNS.settingsSystemInfo} element={<SystemInfoPage />} />
      <Route path={ROUTE_PATTERNS.dailyReport} element={<DailyReportPage />} />
      <Route path={ROUTE_PATTERNS.dailyReportProgress} element={<ProgressOnlyPage />} />
      <Route path={ROUTE_PATTERNS.dailyReportView} element={<DailyReportViewPage />} />
      <Route path={ROUTE_PATTERNS.help} element={<HelpPage />} />
    </Route>,
  ),
)

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <RouterProvider router={router} />
      </ToastProvider>
    </QueryClientProvider>
  )
}
