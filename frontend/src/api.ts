import axios from 'axios'

const client = axios.create({ baseURL: '/api' })

// ── Types ──────────────────────────────────────────────────────────────────

export interface Company {
  id: number
  name: string
  website: string
  stage: string
  location: string
  tech_stack: string[]
  f1_friendly: boolean
}

export interface JobListing {
  id: number
  company_id: number
  company: Company
  role_title: string
  location: string
  apply_url: string
  score: number
  tier: string
  status: string
  cpt_friendly_signal: boolean
  role_description?: string
  recipient_email?: string
  recipient_name?: string
}

export interface RecipientContact {
  contact_name: string | null
  contact_title: string | null
  contact_type: string
  email_guess: string | null
  email_confidence: 'high' | 'medium' | 'low'
  reasoning: string
  linkedin_search_tip?: string
}

export interface EmailDraft {
  id: number
  job_listing_id: number
  subject: string
  body: string
  personalization_notes: string
  status: string
  created_at: string
}

export interface SentEmail {
  id: number
  job_listing_id: number
  company_name: string
  role_title: string
  subject: string
  sent_at: string
  gmail_message_id: string
  status: string
}

export interface DashboardStats {
  total_companies: number
  total_listings: number
  tier1_count: number
  tier2_count: number
  tier3_count: number
  emails_drafted: number
  emails_approved: number
  emails_sent_total: number
  emails_sent_today: number
  daily_limit_remaining: number
}

// ── API ───────────────────────────────────────────────────────────────────

export const api = {
  // Dashboard
  getDashboardStats: () =>
    client.get<DashboardStats>('/dashboard/stats').then((r) => r.data),

  // Companies / Listings
  getListings: (tier?: string) =>
    client
      .get<JobListing[]>('/companies', { params: tier ? { tier } : {} })
      .then((r) => r.data),
  triggerScrape: () => client.post('/companies/scrape').then((r) => r.data),
  scoreAll: () => client.post('/companies/score-all').then((r) => r.data),
  researchListing: (id: number) =>
    client.post(`/companies/research/${id}`).then((r) => r.data),
  setRecipient: (
    listingId: number,
    data: { recipient_email: string; recipient_name?: string }
  ) => client.put<JobListing>(`/companies/listings/${listingId}/recipient`, data).then((r) => r.data),
  findRecipientEmail: (listingId: number) =>
    client.post<RecipientContact>(`/companies/listings/${listingId}/find-email`).then((r) => r.data),

  // Emails
  getEmailPreview: (listingId: number) =>
    client.get<EmailDraft>(`/emails/${listingId}/preview`).then((r) => r.data),
  generateEmail: (listingId: number) =>
    client.post<EmailDraft>(`/emails/${listingId}/generate`).then((r) => r.data),
  updateEmail: (draftId: number, data: { subject: string; body: string }) =>
    client.put<EmailDraft>(`/emails/${draftId}`, data).then((r) => r.data),
  approveEmail: (draftId: number) =>
    client.post(`/emails/${draftId}/approve`).then((r) => r.data),
  skipEmail: (draftId: number) =>
    client.post(`/emails/${draftId}/skip`).then((r) => r.data),
  sendBatch: () => client.post('/emails/send-batch').then((r) => r.data),
  sendTest: () => client.post('/emails/test-send').then((r) => r.data),
  getSentLog: () => client.get<SentEmail[]>('/emails/sent').then((r) => r.data),
}
