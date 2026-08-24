import { NavLink } from 'react-router-dom'
import { ROUTES } from '../constants/routes'
import { t } from '../locales/t'

const NAV_ITEMS = [
  { to: ROUTES.dashboard, labelKey: 'nav.dashboard' },
  { to: ROUTES.goals, labelKey: 'nav.goals' },
  { to: ROUTES.calendar, labelKey: 'nav.calendar' },
  { to: ROUTES.analytics, labelKey: 'nav.analytics' },
  { to: ROUTES.settings, labelKey: 'nav.settings' },
] as const

/** グローバルナビゲーション（仕様書5.1）。 */
export function GlobalNav() {
  return (
    <nav className="flex gap-1 border-b border-gray-200 bg-white px-4 py-2">
      {NAV_ITEMS.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          end={item.to === ROUTES.dashboard}
          className={({ isActive }) =>
            `rounded-md px-3 py-1.5 text-sm font-medium ${
              isActive ? 'bg-blue-50 text-blue-700' : 'text-gray-600 hover:bg-gray-50'
            }`
          }
        >
          {t(item.labelKey)}
        </NavLink>
      ))}
    </nav>
  )
}
