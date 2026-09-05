import { getAuthToken } from './apollo'
import { GRAPHQL_URL } from '../config'

const apiBase = GRAPHQL_URL.replace(/\/graphql\/?$/, '')

export interface PublicDocumentRequestInfo {
  status: string
  expires_at: string
}

export async function publicDocumentRequest(token: string): Promise<PublicDocumentRequestInfo> {
  const response = await fetch(`${apiBase}/api/documents/request/${encodeURIComponent(token)}`)
  if (!response.ok) throw new Error('This upload link is invalid or has expired.')
  return (await response.json()) as PublicDocumentRequestInfo
}

export async function uploadRequestedDocument(
  token: string,
  file: File,
  idempotencyKey: string,
  classification?: string,
): Promise<{ id?: string; file_name?: string; status?: string }> {
  const form = new FormData()
  form.append('file', file)
  form.append('idempotency_key', idempotencyKey)
  if (classification) {
    form.append('classification', classification)
  }
  const response = await fetch(`${apiBase}/api/documents/request/${encodeURIComponent(token)}/upload`, { method: 'POST', body: form })
  if (!response.ok) {
    const detail: unknown = await response.json().catch(() => ({}))
    const message = typeof detail === 'object' && detail !== null && 'detail' in detail && typeof detail.detail === 'string' ? detail.detail : `Upload failed (${response.status})`
    throw new Error(message)
  }
  return (await response.json()) as { id?: string; file_name?: string; status?: string }
}

export async function createDocumentRequest(crewId: string): Promise<{ token: string }> {
  const token = getAuthToken()
  const form = new FormData()
  form.append('crew_id', crewId)
  form.append('expires_in_days', '14')
  const response = await fetch(`${apiBase}/api/documents/requests`, {
    method: 'POST', credentials: 'include', headers: token ? { Authorization: `Bearer ${token}` } : undefined, body: form,
  })
  if (!response.ok) {
    const detail: unknown = await response.json().catch(() => ({}))
    const message = typeof detail === 'object' && detail !== null && 'detail' in detail && typeof detail.detail === 'string' ? detail.detail : 'Could not create a secure upload link.'
    throw new Error(message)
  }
  return response.json() as Promise<{ token: string }>
}

export interface IncomingDocumentReview {
  id: string
  status: string
  document_id: string
  file_name: string
  file_type?: string | null
  file_size?: number | null
  classification?: string | null
  extraction_status?: string | null
  crew_member_id: string
  contractor_name: string
  created_at: string
  claimed_by?: string | null
}

export async function incomingDocumentReviews(): Promise<IncomingDocumentReview[]> {
  const token = getAuthToken()
  const response = await fetch(`${apiBase}/api/documents/review-queue`, {
    credentials: 'include', headers: token ? { Authorization: `Bearer ${token}` } : undefined,
  })
  if (!response.ok) throw new Error('Could not load received documents.')
  return response.json() as Promise<IncomingDocumentReview[]>
}

export async function actionIncomingDocumentReview(
  reviewId: string,
  action: 'approve' | 'reject',
  note?: string,
): Promise<{ id: string; status: string; document_id: string }> {
  const token = getAuthToken()
  const form = new FormData()
  form.append('action', action)
  if (note) form.append('note', note)

  const response = await fetch(
    `${apiBase}/api/documents/review-queue/${encodeURIComponent(reviewId)}/action`,
    {
      method: 'POST',
      credentials: 'include',
      headers: token ? { Authorization: `Bearer ${token}` } : undefined,
      body: form,
    },
  )

  if (!response.ok) {
    const detail: unknown = await response.json().catch(() => ({}))
    const message =
      typeof detail === 'object' && detail !== null && 'detail' in detail && typeof detail.detail === 'string'
        ? detail.detail
        : `Could not ${action} document.`
    throw new Error(message)
  }

  return response.json() as Promise<{ id: string; status: string; document_id: string }>
}

export async function reviewDocumentById(
  documentId: string,
  action: 'approve' | 'reject',
  note?: string,
): Promise<{ id: string | null; status: string; extraction_status: string; document_id: string }> {
  const token = getAuthToken()
  const form = new FormData()
  form.append('action', action)
  if (note) form.append('note', note)

  const response = await fetch(
    `${apiBase}/api/documents/${encodeURIComponent(documentId)}/review`,
    {
      method: 'POST',
      credentials: 'include',
      headers: token ? { Authorization: `Bearer ${token}` } : undefined,
      body: form,
    },
  )

  if (!response.ok) {
    const detail: unknown = await response.json().catch(() => ({}))
    const message =
      typeof detail === 'object' && detail !== null && 'detail' in detail && typeof detail.detail === 'string'
        ? detail.detail
        : `Could not ${action} document.`
    throw new Error(message)
  }

  return response.json() as Promise<{
    id: string | null
    status: string
    extraction_status: string
    document_id: string
  }>
}

export function documentDownloadUrl(documentId: string): string {
  return `${apiBase}/api/documents/${encodeURIComponent(documentId)}/download`
}

export type BE_Classification =
  | 'cert'
  | 'cv'
  | 'identity'
  | 'project'
  | 'compliance'
  | 'performance'

export function feCategoryToBE(category: string): BE_Classification | undefined {
  switch (category) {
    case 'certificate':
      return 'cert'
    case 'cv':
      return 'cv'
    case 'medical':
    case 'seamans_book':
      return 'compliance'
    case 'survey_report':
      return 'project'
    default:
      return undefined
  }
}

export interface UploadResult {
  id: string
  file_name: string
  file_type: string
  file_size: number
  status: string
}

export interface CvPreview {
  full_name?: string | null
  email?: string | null
  phone?: string | null
  nationality?: string | null
  country_of_residence?: string | null
  date_of_birth?: string | null
  gender?: string | null
  languages?: string[] | string | null
  flying_point?: string | null
}

export async function previewCv(file: File): Promise<CvPreview> {
  const token = getAuthToken()
  const form = new FormData()
  form.append('file', file)
  const resp = await fetch(`${apiBase}/api/documents/preview-cv`, {
    method: 'POST',
    credentials: 'include',
    headers: token ? { Authorization: `Bearer ${token}` } : undefined,
    body: form,
  })
  if (!resp.ok) {
    const detail = await resp.json().catch(() => ({}))
    throw new Error(detail?.detail || `Could not read CV (${resp.status})`)
  }
  return resp.json() as Promise<CvPreview>
}

export async function uploadDocument(
  crewId: string,
  file: File,
  classification?: string,
  idempotencyKey?: string
): Promise<UploadResult> {
  const token = getAuthToken()
  const form = new FormData()
  form.append('crew_id', crewId)
  form.append('file', file)
  if (classification) form.append('classification', classification)
  if (idempotencyKey) form.append('idempotency_key', idempotencyKey)

  const resp = await fetch(`${apiBase}/api/documents/upload`, {
    method: 'POST',
    credentials: 'include',
    headers: token ? { Authorization: `Bearer ${token}` } : undefined,
    body: form,
  })

  if (!resp.ok) {
    const detail = await resp.json().catch(() => ({}))
    throw new Error(detail?.detail || `Upload failed (${resp.status})`)
  }

  return (await resp.json()) as UploadResult
}

export async function getDocumentStatus(
  documentId: string
): Promise<{ id: string; file_name: string; extraction_status: string; classification?: string | null }> {
  const token = getAuthToken()
  const resp = await fetch(`${apiBase}/api/documents/${documentId}/status`, {
    credentials: 'include',
    headers: token ? { Authorization: `Bearer ${token}` } : undefined,
  })
  if (!resp.ok) {
    throw new Error(`Status check failed (${resp.status})`)
  }
  return resp.json()
}

export async function deleteDocument(documentId: string): Promise<void> {
  const token = getAuthToken()
  const resp = await fetch(`${apiBase}/api/documents/${documentId}`, {
    method: 'DELETE',
    credentials: 'include',
    headers: token ? { Authorization: `Bearer ${token}` } : undefined,
  })
  if (!resp.ok) {
    const detail = await resp.json().catch(() => ({}))
    throw new Error(detail?.detail || `Delete failed (${resp.status})`)
  }
}
