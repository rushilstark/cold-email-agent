import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  ExternalLink, Mail, ChevronDown, ChevronUp,
  RefreshCw, X, Check, SkipForward, Wand2, AlertCircle,
} from 'lucide-react'
import clsx from 'clsx'
import { api, JobListing, EmailDraft } from '../api'
import TierBadge from '../components/TierBadge'
import ScoreBar from '../components/ScoreBar'

// ── Status badge ──────────────────────────────────────────────────────────

function StatusBadge({ status }: { status: string }) {
  const map: Record<string, string> = {
    pending: 'bg-gray-100 text-gray-600',
    researched: 'bg-blue-100 text-blue-700',
    draft_ready: 'bg-purple-100 text-purple-700',
    approved: 'bg-emerald-100 text-emerald-700',
    sent: 'bg-indigo-100 text-indigo-700',
    skipped: 'bg-red-100 text-red-500',
  }
  return (
    <span className={clsx('px-2 py-0.5 rounded-full text-xs font-semibold capitalize', map[status] ?? 'bg-gray-100 text-gray-500')}>
      {status?.replace('_', ' ') ?? '—'}
    </span>
  )
}

// ── Email Preview Modal ───────────────────────────────────────────────────

interface ModalProps {
  listing: JobListing
  onClose: () => void
}

function EmailModal({ listing, onClose }: ModalProps) {
  const qc = useQueryClient()
  const [subject, setSubject] = useState('')
  const [body, setBody] = useState('')
  const [showNotes, setShowNotes] = useState(false)
  const [draft, setDraft] = useState<EmailDraft | null>(null)
  const [recipientEmail, setRecipientEmail] = useState(listing.recipient_email || '')
  const [recipientName, setRecipientName] = useState(listing.recipient_name || '')
  const [contactSuggestion, setContactSuggestion] = useState<any>(null)
  const [validationError, setValidationError] = useState<string | null>(null)
  const [cptStrategy, setCptStrategy] = useState<'natural' | 'explicit' | 'hidden'>('natural')

  const previewQ = useQuery<EmailDraft>({
    queryKey: ['email-preview', listing.id],
    queryFn: () => api.getEmailPreview(listing.id),
    retry: false,
    staleTime: 0,
  })

  // Sync local state when data arrives
  const draftData = draft ?? previewQ.data ?? null
  const displaySubject = draft ? subject : (previewQ.data?.subject ?? '')
  const displayBody = draft ? body : (previewQ.data?.body ?? '')
  const notes = draftData?.personalization_notes ?? ''

  const findContact = useMutation({
    mutationFn: () => api.findRecipientEmail(listing.id),
    onSuccess: (data) => {
      setContactSuggestion(data)
      if (data.email_guess) setRecipientEmail(data.email_guess)
      if (data.contact_name) setRecipientName(data.contact_name)
      qc.invalidateQueries({ queryKey: ['listings'] })
    },
  })

  const saveRecipient = useMutation({
    mutationFn: () =>
      api.setRecipient(listing.id, {
        recipient_email: recipientEmail,
        recipient_name: recipientName,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['listings'] })
    },
  })

  const generate = useMutation({
    mutationFn: () => api.generateEmail(listing.id),
    onSuccess: (data) => {
      setDraft(data)
      setSubject(data.subject)
      setBody(data.body)
      qc.invalidateQueries({ queryKey: ['listings'] })
    },
  })

  const save = useMutation({
    mutationFn: async () => {
      if (!draftData) throw new Error('No draft')
      if (recipientEmail !== listing.recipient_email || recipientName !== listing.recipient_name) {
        await api.setRecipient(listing.id, {
          recipient_email: recipientEmail,
          recipient_name: recipientName,
        })
      }
      return api.updateEmail(draftData.id, { subject: displaySubject, body: displayBody })
    },
    onSuccess: (data) => {
      setDraft(data)
      qc.invalidateQueries({ queryKey: ['listings'] })
    },
  })

  const approve = useMutation({
    mutationFn: async () => {
      if (!draftData) throw new Error('No draft')
      if (!recipientEmail || !recipientEmail.includes('@')) {
        throw new Error('Please enter a valid Recruiter / Hiring contact email before approving.')
      }
      // Save recipient first
      await api.setRecipient(listing.id, {
        recipient_email: recipientEmail,
        recipient_name: recipientName,
      })
      return api.approveEmail(draftData.id)
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['listings'] })
      onClose()
    },
    onError: (err: any) => {
      setValidationError(err.message || 'Failed to approve email')
    },
  })

  const skip = useMutation({
    mutationFn: () => {
      if (!draftData) throw new Error('No draft')
      return api.skipEmail(draftData.id)
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['listings'] })
      onClose()
    },
  })

  const hasDraft = !!draftData
  const busy = generate.isPending || approve.isPending || skip.isPending || findContact.isPending

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-3xl max-h-[90vh] flex flex-col overflow-hidden">
        {/* Modal header */}
        <div className="flex items-start justify-between px-6 py-4 border-b border-gray-100 flex-shrink-0">
          <div>
            <h2 className="text-base font-bold text-gray-900">{listing.company.name}</h2>
            <p className="text-sm text-gray-500 mt-0.5">{listing.role_title} · {listing.location}</p>
            <div className="flex items-center gap-2 mt-2">
              <TierBadge tier={listing.tier} />
              {listing.cpt_friendly_signal && (
                <span className="px-2 py-0.5 bg-emerald-100 text-emerald-700 text-xs font-semibold rounded-full">
                  CPT OK
                </span>
              )}
              {listing.score > 0 && (
                <div className="flex items-center gap-2 w-32">
                  <ScoreBar score={listing.score} />
                </div>
              )}
            </div>
          </div>
          <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-gray-100 text-gray-400 hover:text-gray-600 transition-colors">
            <X size={18} />
          </button>
        </div>

        {/* Modal body */}
        <div className="flex-1 overflow-y-auto px-6 py-5 space-y-4">
          {/* Target Recruiter / Contact section */}
          <div className="bg-indigo-50/60 border border-indigo-100 rounded-xl p-4">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-bold text-indigo-900 uppercase tracking-wider flex items-center gap-1.5">
                <Mail size={14} className="text-indigo-600" />
                Target Recruiter / Contact
              </span>
              <button
                onClick={() => findContact.mutate()}
                disabled={findContact.isPending}
                className="inline-flex items-center gap-1.5 text-xs font-semibold px-2.5 py-1 bg-white text-indigo-700 border border-indigo-200 rounded-md shadow-xs hover:bg-indigo-50 transition-colors disabled:opacity-50"
              >
                {findContact.isPending ? <RefreshCw size={12} className="animate-spin" /> : <Wand2 size={12} />}
                AI Find Contact
              </button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mt-2">
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Recipient Name</label>
                <input
                  type="text"
                  placeholder="e.g. Sarah Jenkins (Recruiter / CTO)"
                  value={recipientName}
                  onChange={(e) => {
                    setRecipientName(e.target.value)
                    setValidationError(null)
                  }}
                  className="w-full px-3 py-1.5 bg-white border border-gray-200 rounded-lg text-xs font-medium focus:outline-none focus:ring-2 focus:ring-indigo-300"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">
                  Recipient Email <span className="text-rose-500">*</span>
                </label>
                <input
                  type="email"
                  placeholder="e.g. sjenkins@company.com"
                  value={recipientEmail}
                  onChange={(e) => {
                    setRecipientEmail(e.target.value)
                    setValidationError(null)
                  }}
                  className="w-full px-3 py-1.5 bg-white border border-gray-200 rounded-lg text-xs font-medium focus:outline-none focus:ring-2 focus:ring-indigo-300"
                />
              </div>
            </div>

            {/* AI Suggestion breakdown */}
            {contactSuggestion && (
              <div className="mt-3 pt-2.5 border-t border-indigo-100 text-xs text-indigo-950 flex flex-col gap-1">
                <div className="flex items-center justify-between">
                  <span className="font-semibold">{contactSuggestion.contact_title}</span>
                  <span className={clsx(
                    'px-2 py-0.5 rounded-full text-[10px] font-bold uppercase',
                    contactSuggestion.email_confidence === 'high' ? 'bg-emerald-100 text-emerald-800' : 'bg-amber-100 text-amber-800'
                  )}>
                    {contactSuggestion.email_confidence} confidence
                  </span>
                </div>
                <p className="text-gray-600 text-[11px]">{contactSuggestion.reasoning}</p>
                {contactSuggestion.linkedin_search_tip && (
                  <a
                    href={`https://www.linkedin.com/search/results/all/?keywords=${encodeURIComponent(
                      `${listing.company.name} ${contactSuggestion.contact_title || 'recruiter'}`
                    )}`}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-1 text-[11px] text-indigo-600 hover:text-indigo-800 font-semibold mt-1"
                  >
                    <span>Verify on LinkedIn</span>
                    <ExternalLink size={10} />
                  </a>
                )}
              </div>
            )}
          </div>

          {validationError && (
            <div className="p-3 bg-rose-50 border border-rose-200 text-rose-700 text-xs rounded-lg flex items-center gap-2">
              <AlertCircle size={14} />
              <span>{validationError}</span>
            </div>
          )}

          {previewQ.isLoading && !draft && (
            <div className="flex items-center justify-center py-12">
              <RefreshCw size={20} className="animate-spin text-primary-400" />
            </div>
          )}

          {(previewQ.isError && !hasDraft) && (
            <div className="flex flex-col items-center gap-3 py-8 text-gray-400">
              <AlertCircle size={28} />
              <p className="text-sm text-center">No draft yet. Click <strong>Generate New</strong> to create one with AI.</p>
            </div>
          )}

          {hasDraft && (
            <>
              {/* Subject */}
              <div>
                <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1.5">
                  Subject
                </label>
                <input
                  type="text"
                  value={draft ? subject : displaySubject}
                  onChange={(e) => { setSubject(e.target.value); if (!draft && draftData) setDraft(draftData) }}
                  className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-300 font-medium"
                />
              </div>

              {/* Body */}
              <div>
                <div className="flex items-center justify-between mb-1.5">
                  <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wide">
                    Email Body (Auto-attaches Resume PDF)
                  </label>
                  <span className="text-[11px] text-gray-400">Personalized for {listing.company.name}</span>
                </div>
                <textarea
                  value={draft ? body : displayBody}
                  onChange={(e) => { setBody(e.target.value); if (!draft && draftData) setDraft(draftData) }}
                  rows={14}
                  className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-300 font-mono resize-y leading-relaxed"
                />
              </div>

              {/* Personalization notes */}
              {notes && (
                <div className="rounded-lg border border-gray-200 overflow-hidden">
                  <button
                    onClick={() => setShowNotes((v) => !v)}
                    className="w-full flex items-center justify-between px-4 py-2.5 bg-gray-50 text-sm font-medium text-gray-600 hover:bg-gray-100 transition-colors"
                  >
                    <span>📝 Personalization Notes & CPT Strategy</span>
                    {showNotes ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                  </button>
                  {showNotes && (
                    <div className="px-4 py-3 bg-gray-50 text-xs text-gray-500 font-mono whitespace-pre-wrap border-t border-gray-200">
                      {notes}
                    </div>
                  )}
                </div>
              )}
            </>
          )}

          {/* Error states */}
          {generate.isError && (
            <p className="text-xs text-red-500 flex items-center gap-1">
              <AlertCircle size={13} /> Generation failed — check backend logs
            </p>
          )}
        </div>

        {/* Footer actions */}
        <div className="flex items-center justify-between px-6 py-4 border-t border-gray-100 bg-gray-50/60 flex-shrink-0">
          <button
            className="btn-secondary"
            onClick={() => generate.mutate()}
            disabled={busy}
          >
            {generate.isPending ? <RefreshCw size={14} className="animate-spin" /> : <Wand2 size={14} />}
            Regenerate Email
          </button>

          <div className="flex items-center gap-2">
            {hasDraft && (
              <button
                className="btn-secondary"
                onClick={() => save.mutate()}
                disabled={busy || save.isPending}
              >
                {save.isPending ? <RefreshCw size={14} className="animate-spin" /> : null}
                Save Edits
              </button>
            )}
            <button
              className="btn-danger"
              onClick={() => skip.mutate()}
              disabled={busy || !hasDraft}
            >
              <SkipForward size={14} />
              Skip
            </button>
            <button
              className="btn-success"
              onClick={() => approve.mutate()}
              disabled={busy || !hasDraft}
            >
              <Check size={14} />
              Approve for Batch
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

// ── Companies Page ────────────────────────────────────────────────────────

const TIERS = ['All', 'tier1', 'tier2', 'tier3']
const STATUSES = ['All', 'pending', 'researched', 'draft_ready', 'approved', 'sent', 'skipped']

export default function Companies() {
  const [tierFilter, setTierFilter] = useState('All')
  const [statusFilter, setStatusFilter] = useState('All')
  const [selectedListing, setSelectedListing] = useState<JobListing | null>(null)

  const { data: listings = [], isLoading } = useQuery<JobListing[]>({
    queryKey: ['listings', tierFilter],
    queryFn: () => api.getListings(tierFilter === 'All' ? undefined : tierFilter),
    refetchInterval: 15_000,
  })

  const filtered = statusFilter === 'All'
    ? listings
    : listings.filter((l) => l.status === statusFilter)

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">Companies & Listings</h2>
          <p className="text-sm text-gray-500 mt-1">
            {filtered.length} listing{filtered.length !== 1 ? 's' : ''} shown
          </p>
        </div>
      </div>

      {/* Filter bar */}
      <div className="flex flex-wrap items-center gap-4">
        {/* Tier filter */}
        <div className="flex items-center gap-1 bg-white border border-gray-200 rounded-lg p-1">
          {TIERS.map((t) => (
            <button
              key={t}
              onClick={() => setTierFilter(t)}
              className={clsx(
                'px-3 py-1.5 rounded-md text-xs font-semibold transition-colors',
                tierFilter === t
                  ? 'bg-primary-500 text-white shadow-sm'
                  : 'text-gray-500 hover:text-gray-800 hover:bg-gray-100',
              )}
            >
              {t === 'All' ? 'All Tiers' : t.replace('tier', 'Tier ')}
            </button>
          ))}
        </div>

        {/* Status filter */}
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="px-3 py-1.5 text-xs border border-gray-200 rounded-lg bg-white text-gray-600 font-medium focus:outline-none focus:ring-2 focus:ring-primary-300"
        >
          {STATUSES.map((s) => (
            <option key={s} value={s}>
              {s === 'All' ? 'All Statuses' : s.replace('_', ' ')}
            </option>
          ))}
        </select>
      </div>

      {/* Table */}
      <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden">
        {isLoading ? (
          <div className="flex items-center justify-center py-16">
            <RefreshCw size={20} className="animate-spin text-primary-400" />
          </div>
        ) : filtered.length === 0 ? (
          <div className="flex flex-col items-center gap-3 py-16 text-gray-400">
            <AlertCircle size={28} />
            <p className="text-sm">No listings match your filters.</p>
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100 bg-gray-50/80">
                {['Company', 'Role', 'Location', 'Score', 'Tier', 'Recipient Contact', 'Status', ''].map((h) => (
                  <th
                    key={h}
                    className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide"
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {filtered.map((listing) => (
                <tr key={listing.id} className="hover:bg-gray-50/70 transition-colors">
                  {/* Company */}
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-1.5">
                      <span className="font-semibold text-gray-900">{listing.company.name}</span>
                      {listing.company.website && (
                        <a
                          href={listing.company.website}
                          target="_blank"
                          rel="noreferrer"
                          className="text-gray-400 hover:text-primary-500 transition-colors"
                          onClick={(e) => e.stopPropagation()}
                        >
                          <ExternalLink size={12} />
                        </a>
                      )}
                    </div>
                    <p className="text-xs text-gray-400 mt-0.5">{listing.company.stage}</p>
                  </td>

                  {/* Role */}
                  <td className="px-4 py-3">
                    <span className="font-medium text-gray-800">{listing.role_title}</span>
                  </td>

                  {/* Location + CPT */}
                  <td className="px-4 py-3">
                    <div className="flex flex-col gap-1">
                      <span className="text-gray-600">{listing.location}</span>
                      {listing.cpt_friendly_signal && (
                        <span className="inline-flex w-fit px-1.5 py-0.5 bg-emerald-100 text-emerald-700 text-xs font-semibold rounded-full">
                          CPT OK
                        </span>
                      )}
                    </div>
                  </td>

                  {/* Score */}
                  <td className="px-4 py-3 w-36">
                    {listing.score > 0 ? (
                      <ScoreBar score={listing.score} />
                    ) : (
                      <span className="text-xs text-gray-400">—</span>
                    )}
                  </td>

                  {/* Tier */}
                  <td className="px-4 py-3">
                    <TierBadge tier={listing.tier} />
                  </td>

                  {/* Recipient Contact */}
                  <td className="px-4 py-3">
                    {listing.recipient_email ? (
                      <div className="flex items-center gap-1 text-xs text-emerald-800 font-medium bg-emerald-50 px-2 py-0.5 rounded-md border border-emerald-100 w-fit max-w-[160px]">
                        <Check size={11} className="text-emerald-600 shrink-0" />
                        <span className="truncate">{listing.recipient_email}</span>
                      </div>
                    ) : (
                      <span className="text-[11px] text-amber-700 bg-amber-50 px-2 py-0.5 rounded border border-amber-100 font-medium">
                        Needs contact
                      </span>
                    )}
                  </td>

                  {/* Status */}
                  <td className="px-4 py-3">
                    <StatusBadge status={listing.status} />
                  </td>

                  {/* Actions */}
                  <td className="px-4 py-3">
                    <button
                      onClick={() => setSelectedListing(listing)}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-primary-50 text-primary-600 hover:bg-primary-100 rounded-lg text-xs font-semibold transition-colors"
                    >
                      <Mail size={12} />
                      Preview Email
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Email modal */}
      {selectedListing && (
        <EmailModal
          listing={selectedListing}
          onClose={() => setSelectedListing(null)}
        />
      )}
    </div>
  )
}
