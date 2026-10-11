import { Routes, Route, NavLink } from 'react-router-dom'
import { LayoutDashboard, Building2, Send, FlaskConical } from 'lucide-react'
import clsx from 'clsx'
import Dashboard from './pages/Dashboard'
import Companies from './pages/Companies'
import SentLog from './pages/SentLog'

const navItems = [
  { to: '/', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/companies', icon: Building2, label: 'Companies' },
  { to: '/sent', icon: Send, label: 'Sent Log' },
]

export default function App() {
  return (
    <div className="flex h-screen bg-gray-50 overflow-hidden">
      {/* Sidebar */}
      <aside className="w-64 flex-shrink-0 flex flex-col bg-sidebar text-white">
        {/* Logo */}
        <div className="px-6 py-5 border-b border-slate-700/60">
          <h1 className="text-lg font-bold tracking-tight">🚀 CPT Email Agent</h1>
          <p className="text-xs text-slate-400 mt-0.5">by Rushil Reddy Chirla</p>
        </div>

        {/* Dry-run badge */}
        <div className="px-6 py-3">
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 bg-amber-400/10 text-amber-300 text-xs font-semibold rounded-full border border-amber-400/20">
            <FlaskConical size={11} />
            DRY RUN MODE
          </span>
        </div>

        {/* Nav */}
        <nav className="flex-1 px-3 pb-4 space-y-0.5">
          {navItems.map(({ to, icon: Icon, label }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              className={({ isActive }) =>
                clsx(
                  'flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors',
                  isActive
                    ? 'bg-primary-600 text-white'
                    : 'text-slate-400 hover:bg-slate-800 hover:text-white',
                )
              }
            >
              <Icon size={16} />
              {label}
            </NavLink>
          ))}
        </nav>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-slate-700/60">
          <p className="text-xs text-slate-500">FastAPI @ localhost:8001</p>
          <div className="flex items-center gap-1.5 mt-1">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
            <span className="text-xs text-slate-400">Backend connected</span>
          </div>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-y-auto">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/companies" element={<Companies />} />
          <Route path="/sent" element={<SentLog />} />
        </Routes>
      </main>
    </div>
  )
}
