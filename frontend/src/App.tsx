import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { ROUTE_PATTERNS } from './constants/routes'
import { t } from './locales/t'
import { ToastProvider } from './components/Toast'
import { GlobalNav } from './components/GlobalNav'
import { DashboardPage } from './pages/DashboardPage'
import { ComingSoonPage } from './pages/ComingSoonPage'

const queryClient = new QueryClient()

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <BrowserRouter>
          <GlobalNav />
          <Routes>
            <Route path={ROUTE_PATTERNS.dashboard} element={<DashboardPage />} />
            <Route path={ROUTE_PATTERNS.goals} element={<ComingSoonPage title={t('nav.goals')} />} />
            <Route path={ROUTE_PATTERNS.goalDetail} element={<ComingSoonPage title={t('nav.goals')} />} />
            <Route path={ROUTE_PATTERNS.calendar} element={<ComingSoonPage title={t('nav.calendar')} />} />
            <Route path={ROUTE_PATTERNS.analytics} element={<ComingSoonPage title={t('nav.analytics')} />} />
            <Route path={ROUTE_PATTERNS.settings} element={<ComingSoonPage title={t('nav.settings')} />} />
            <Route
              path={ROUTE_PATTERNS.dailyReport}
              element={<ComingSoonPage title={t('dashboard.reportButton.label')} />}
            />
            <Route
              path={ROUTE_PATTERNS.dailyReportView}
              element={<ComingSoonPage title={t('dashboard.reportButton.label')} />}
            />
          </Routes>
        </BrowserRouter>
      </ToastProvider>
    </QueryClientProvider>
  )
}
