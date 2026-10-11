import { useQuery } from '@tanstack/react-query'
import { RefreshCw, Send, ExternalLink, Inbox } from 'lucide-react'
import { api, SentEmail } from '../api'

function formatDate(iso: string) {
  try {
    return new Intl.DateTimeFormat('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    }).format(new Date(iso))
  } catch {
    return iso
  }
}

export default function SentLog() {
  const { data: sent = [], isLoading } = useQuery<SentEmail[]>({
    queryKey: ['sent-log'],
    queryFn: api.getSentLog,
    refetchInterval: 60_000,
  })

  return (
    <div className="p-8 max-w-6xl mx-auto space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-bold text-gray-900">Sent Log</h2>
        <p className="text-sm text-gray-500 mt-1">
          All emails dispatched via Gmail API
        </p>
      </div>

      {/* Table */}
      <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden">
        {isLoading ? (
          <div className="flex items-center justify-center py-16">
            <RefreshCw size={20} className="animate-spin text-primary-400" />
          </div>
        ) : sent.length === 0 ? (
          <div className="flex flex-col items-center gap-4 py-20 text-gray-400">
            <div className="p-4 bg-gray-50 rounded-2xl">
              <Inbox size={40} className="text-gray-300" />
            </div>
            <div className="text-center">
              <p className="font-semibold text-gray-500">No emails sent yet</p>
              <p className="text-sm mt-1">Approve some drafts from the Companies page, then run a Send Batch.</p>
            </div>
            <div className="flex items-center gap-2 px-4 py-2 bg-primary-50 rounded-xl text-sm text-primary-600 font-medium">
              <Send size={14} />
              Ready to launch your first batch?
            </div>
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100 bg-gray-50/80">
                {['Company', 'Role', 'Subject', 'Sent At', 'Gmail ID'].map((h) => (
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
              {sent.map((email) => (
                <tr key={email.id} className="hover:bg-gray-50/70 transition-colors">
                  <td className="px-4 py-3 font-semibold text-gray-900">
                    {email.company_name}
                  </td>
                  <td className="px-4 py-3 text-gray-600">{email.role_title}</td>
                  <td className="px-4 py-3 text-gray-700 max-w-xs truncate">
                    {email.subject}
                  </td>
                  <td className="px-4 py-3 text-gray-500 whitespace-nowrap">
                    {formatDate(email.sent_at)}
                  </td>
                  <td className="px-4 py-3">
                    {email.gmail_message_id ? (
                      <a
                        href={`https://mail.google.com/mail/u/0/#sent/${email.gmail_message_id}`}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-flex items-center gap-1 text-primary-500 hover:text-primary-700 font-mono text-xs underline underline-offset-2"
                      >
                        {email.gmail_message_id.slice(0, 16)}…
                        <ExternalLink size={11} />
                      </a>
                    ) : (
                      <span className="text-gray-400 text-xs">—</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {sent.length > 0 && (
        <p className="text-xs text-gray-400 text-right">
          {sent.length} email{sent.length !== 1 ? 's' : ''} total
        </p>
      )}
    </div>
  )
}
