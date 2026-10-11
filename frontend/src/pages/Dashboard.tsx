import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Briefcase, Star, MailCheck, Gauge,
  Search, Bot, Send, FlaskConical,
  TrendingUp, AlertCircle, RefreshCw,
} from 'lucide-react'
import clsx from 'clsx'
import { api, DashboardStats } from '../api'

// ── Stat Card ─────────────────────────────────────────────────────────────

interface StatCardProps {
  label: string
  value: number | string
  icon: React.ElementType
  iconColor: string
  badge?: React.ReactNode
  sub?: string
}

function StatCard({ label, value, icon: Icon, iconColor, badge, sub }: StatCardProps) {
  return (
    <div className="card flex items-start gap-4">
      <div className={clsx('p-2.5 rounded-lg', iconColor)}>
        <Icon size={20} className="text-white" />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm text-gray-500 font-medium">{label}</p>
        <div className="flex items-baseline gap-2 mt-0.5">
          <p className="text-2xl font-bold text-gray-900">{value}</p>
          {badge}
        </div>
        {sub && <p className="text-xs text-gray-400 mt-0.5">{sub}</p>}
      </div>
    </div>
  )
}

// ── Action Button ─────────────────────────────────────────────────────────

interface ActionBtnProps {
  label: string
  icon: React.ElementType
  onClick: () => void
  loading: boolean
  variant?: 'primary' | 'success' | 'warning' | 'secondary'
}

function ActionBtn({ label, icon: Icon, onClick, loading, variant = 'primary' }: ActionBtnProps) {
  const styles = clsx(
    'flex items-center gap-2 px-5 py-2.5 rounded-xl font-semibold text-sm transition-all shadow-sm disabled:opacity-50 disabled:cursor-not-allowed',
    {
      'bg-primary-500 hover:bg-primary-600 text-white': variant === 'primary',
      'bg-emerald-500 hover:bg-emerald-600 text-white': variant === 'success',
      'bg-amber-500 hover:bg-amber-600 text-white': variant === 'warning',
      'bg-white hover:bg-gray-50 text-gray-700 border border-gray-200': variant === 'secondary',
    },
  )
  return (
    <button className={styles} onClick={onClick} disabled={loading}>
      {loading ? (
        <RefreshCw size={15} className="animate-spin" />
      ) : (
        <Icon size={15} />
      )}
      {label}
    </button>
  )
}

// ── Tier Card ─────────────────────────────────────────────────────────────

function TierCard({
  tier,
  count,
  color,
  description,
}: {
  tier: string
  count: number
  color: 'green' | 'amber' | 'red'
  description: string
}) {
  const ring = { green: 'border-emerald-200', amber: 'border-amber-200', red: 'border-red-200' }[color]
  const numColor = { green: 'text-emerald-600', amber: 'text-amber-600', red: 'text-red-600' }[color]
  const bg = { green: 'bg-emerald-50', amber: 'bg-amber-50', red: 'bg-red-50' }[color]

  return (
    <div className={clsx('rounded-xl border-2 p-5 flex flex-col gap-2', ring, bg)}>
      <div className="flex items-center justify-between">
        <span className="text-sm font-semibold text-gray-600">{tier}</span>
        <TrendingUp size={16} className={numColor} />
      </div>
      <p className={clsx('text-4xl font-black', numColor)}>{count}</p>
      <p className="text-xs text-gray-500">{description}</p>
    </div>
  )
}

// ── Dashboard Page ────────────────────────────────────────────────────────

export default function Dashboard() {
  const qc = useQueryClient()

  const { data: stats, isLoading, isError } = useQuery<DashboardStats>({
    queryKey: ['dashboard'],
    queryFn: api.getDashboardStats,
    refetchInterval: 30_000,
  })

  const scrape = useMutation({
    mutationFn: api.triggerScrape,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['dashboard'] }),
  })

  const score = useMutation({
    mutationFn: api.scoreAll,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['dashboard'] }),
  })

  const sendBatch = useMutation({
    mutationFn: api.sendBatch,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['dashboard'] }),
  })

  const testSend = useMutation({
    mutationFn: api.sendTest,
  })

  const handleSendBatch = () => {
    if (window.confirm('Send the next batch of approved emails? This will use real Gmail send.')) {
      sendBatch.mutate()
    }
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <RefreshCw size={24} className="animate-spin text-primary-400" />
      </div>
    )
  }

  if (isError) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="flex flex-col items-center gap-3 text-gray-400">
          <AlertCircle size={32} />
          <p className="text-sm">Could not reach backend — is FastAPI running on :8000?</p>
        </div>
      </div>
    )
  }

  const s = stats!
  const dailyPct = s.daily_limit_remaining > 0
    ? Math.round((s.daily_limit_remaining / 10) * 100)
    : 0

  return (
    <div className="p-8 max-w-6xl mx-auto space-y-8">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-bold text-gray-900">Dashboard</h2>
        <p className="text-sm text-gray-500 mt-1">
          CPT-aware internship sourcing & outreach pipeline
        </p>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-2 xl:grid-cols-4 gap-4">
        <StatCard
          label="Total Opportunities"
          value={s.total_listings}
          icon={Briefcase}
          iconColor="bg-primary-500"
          sub={`from ${s.total_companies} companies`}
        />
        <StatCard
          label="Tier 1 Matches"
          value={s.tier1_count}
          icon={Star}
          iconColor="bg-emerald-500"
          badge={
            <span className="text-xs px-2 py-0.5 bg-emerald-100 text-emerald-700 rounded-full font-semibold">
              High CPT signal
            </span>
          }
        />
        <StatCard
          label="Emails Sent"
          value={s.emails_sent_total}
          icon={MailCheck}
          iconColor="bg-indigo-500"
          sub={`${s.emails_sent_today} sent today · ${s.emails_approved} approved`}
        />
        <StatCard
          label="Daily Remaining"
          value={`${s.daily_limit_remaining} / 10`}
          icon={Gauge}
          iconColor="bg-slate-500"
          sub={`${dailyPct}% quota left`}
        />
      </div>

      {/* Action buttons */}
      <div className="card">
        <h3 className="text-sm font-semibold text-gray-700 mb-4">Pipeline Actions</h3>
        <div className="flex flex-wrap gap-3">
          <ActionBtn
            label="🔍 Scrape New Jobs"
            icon={Search}
            onClick={() => scrape.mutate()}
            loading={scrape.isPending}
            variant="primary"
          />
          <ActionBtn
            label="🤖 Score All"
            icon={Bot}
            onClick={() => score.mutate()}
            loading={score.isPending}
            variant="primary"
          />
          <ActionBtn
            label="📨 Send Batch"
            icon={Send}
            onClick={handleSendBatch}
            loading={sendBatch.isPending}
            variant="success"
          />
          <ActionBtn
            label="🧪 Test Email"
            icon={FlaskConical}
            onClick={() => testSend.mutate()}
            loading={testSend.isPending}
            variant="secondary"
          />
        </div>

        {/* Mutation status messages */}
        {(scrape.isSuccess || score.isSuccess || sendBatch.isSuccess || testSend.isSuccess) && (
          <p className="mt-3 text-xs text-emerald-600 font-medium flex items-center gap-1">
            <MailCheck size={13} /> Action completed successfully
          </p>
        )}
        {(scrape.isError || score.isError || sendBatch.isError || testSend.isError) && (
          <p className="mt-3 text-xs text-red-500 font-medium flex items-center gap-1">
            <AlertCircle size={13} /> Action failed — check backend logs
          </p>
        )}
      </div>

      {/* Tier breakdown */}
      <div>
        <h3 className="text-sm font-semibold text-gray-700 mb-4">Tier Breakdown</h3>
        <div className="grid grid-cols-3 gap-4">
          <TierCard
            tier="Tier 1"
            count={s.tier1_count}
            color="green"
            description="Strong CPT signal · Highest priority"
          />
          <TierCard
            tier="Tier 2"
            count={s.tier2_count}
            color="amber"
            description="Moderate signal · Worth a try"
          />
          <TierCard
            tier="Tier 3"
            count={s.tier3_count}
            color="red"
            description="Low signal · Low priority"
          />
        </div>
      </div>

      {/* Email funnel */}
      <div className="card">
        <h3 className="text-sm font-semibold text-gray-700 mb-4">Email Funnel</h3>
        <div className="flex items-center gap-3 text-sm">
          {[
            { label: 'Drafted', count: s.emails_drafted, color: 'bg-blue-100 text-blue-700' },
            { label: 'Approved', count: s.emails_approved, color: 'bg-emerald-100 text-emerald-700' },
            { label: 'Sent Today', count: s.emails_sent_today, color: 'bg-primary-100 text-primary-700' },
            { label: 'Sent Total', count: s.emails_sent_total, color: 'bg-slate-100 text-slate-700' },
          ].map(({ label, count, color }) => (
            <div key={label} className="flex-1 flex flex-col items-center gap-1 p-3 rounded-lg bg-gray-50">
              <span className={clsx('text-lg font-bold px-2 py-0.5 rounded', color)}>{count}</span>
              <span className="text-xs text-gray-500">{label}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
