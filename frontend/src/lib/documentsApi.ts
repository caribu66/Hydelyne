import { GRAPHQL_URL } from '../config'

const apiBase = GRAPHQL_URL.replace(/\/graphql\/?$/, '')

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}

interface PublicUploadResult {
  id: string
  file_name: string
  status: string
}

function isExtractionStatus(value: unknown): value is string {
  return value === 'pending'
    || value === 'processing'
    || value === 'extracted'
    || value === 'failed'
    || value === 'needs_review'
    || value === 'awaiting_review'
    || value === 'approved'
    || value === 'rejected'
}

function isReviewStatus(value: unknown): value is string {
  return value === 'unread' || value === 'claimed' || value === 'processing' || value === 'resolved' || value === 'rejected'
}

function parsePublicUploadResult(value: unknown): PublicUploadResult {
  if (
    !isRecord(value)
    || typeof value.id !== 'string'
    || typeof value.file_name !== 'string'
    || !isExtractionStatus(value.status)
  ) {
    throw new Error('Server returned an invalid upload response.')
  }
  return { id: value.id, file_name: value.file_name, status: value.status }
}

export interface PublicDocumentRequestInfo {
  status: string
  expires_at: string
}

export async function publicDocumentRequest(token: string): Promise<PublicDocumentRequestInfo> {
  const response = await fetch(`${apiBase}/api/documents/request/${encodeURIComponent(token)}`)
  if (!response.ok) throw new Error('This upload link is invalid or has expired.')
  const value: unknown = await response.json()
  if (
    !isRecord(value)
    || value.status !== 'active'
    || typeof value.expires_at !== 'string'
    || !Number.isFinite(Date.parse(value.expires_at))
  ) {
    throw new Error('This upload link is invalid or has expired.')
  }
  return { status: 'active', expires_at: value.expires_at }
}

export async function uploadRequestedDocument(
  token: string,
  file: File,
  idempotencyKey: string,
  classification?: string,
): Promise<PublicUploadResult> {
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
  const result = parsePublicUploadResult(await response.json())
  if (result.status === 'failed') {
    // The API has persisted the idempotent document but could not dispatch
    // extraction. Keep the caller in its retry state; treating HTTP 200 as
    // success would falsely tell the contractor the document is processing.
    throw new Error('Document received, but processing could not start. Please try again.')
  }
  return result
}

export async function createDocumentRequest(crewId: string): Promise<{ token: string }> {
  const form = new FormData()
  form.append('crew_id', crewId)
  form.append('expires_in_days', '14')
  const response = await fetch(`${apiBase}/api/documents/requests`, {
    method: 'POST', credentials: 'include', body: form,
  })
  if (!response.ok) {
    const detail: unknown = await response.json().catch(() => ({}))
    const message = typeof detail === 'object' && detail !== null && 'detail' in detail && typeof detail.detail === 'string' ? detail.detail : 'Could not create a secure upload link.'
    throw new Error(message)
  }
  const result: unknown = await response.json()
  if (!isRecord(result) || typeof result.token !== 'string' || result.token.length === 0) {
    throw new Error('Server returned an invalid upload link response.')
  }
  return { token: result.token }
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

function isString(value: unknown): value is string {
  return typeof value === 'string'
}

function parseIncomingDocumentReviews(value: unknown): IncomingDocumentReview[] {
  if (!Array.isArray(value)) {
    throw new Error('Server returned an invalid document review queue.')
  }
  return value.map((item) => {
    if (
      !isRecord(item)
      || !isString(item.id)
      || !isReviewStatus(item.status)
      || !isString(item.document_id)
      || !isString(item.file_name)
      || !isString(item.crew_member_id)
      || !isString(item.contractor_name)
      || !isString(item.created_at)
    ) {
      throw new Error('Server returned an invalid document review queue.')
    }
    return {
      id: item.id,
      status: item.status,
      document_id: item.document_id,
      file_name: item.file_name,
      file_type: typeof item.file_type === 'string' || item.file_type === null ? item.file_type : undefined,
      file_size: typeof item.file_size === 'number' || item.file_size === null ? item.file_size : undefined,
      classification: typeof item.classification === 'string' || item.classification === null ? item.classification : undefined,
      extraction_status: typeof item.extraction_status === 'string' || item.extraction_status === null ? item.extraction_status : undefined,
      crew_member_id: item.crew_member_id,
      contractor_name: item.contractor_name,
      created_at: item.created_at,
      claimed_by: typeof item.claimed_by === 'string' || item.claimed_by === null ? item.claimed_by : undefined,
    }
  })
}

function parseReviewActionResult(
  value: unknown,
  action: 'approve' | 'reject',
): { id: string; status: string; document_id: string } {
  if (
    !isRecord(value)
    || !isString(value.id)
    || !isReviewStatus(value.status)
    || !isString(value.document_id)
    || value.status !== (action === 'approve' ? 'resolved' : 'rejected')
  ) {
    throw new Error('Server returned an invalid document review response.')
  }
  return { id: value.id, status: value.status, document_id: value.document_id }
}

export async function incomingDocumentReviews(): Promise<IncomingDocumentReview[]> {
  const response = await fetch(`${apiBase}/api/documents/review-queue`, { credentials: 'include' })
  if (!response.ok) throw new Error('Could not load received documents.')
  return parseIncomingDocumentReviews(await response.json())
}

export async function actionIncomingDocumentReview(
  reviewId: string,
  action: 'approve' | 'reject',
  note?: string,
): Promise<{ id: string; status: string; document_id: string }> {
  const form = new FormData()
  form.append('action', action)
  if (note) form.append('note', note)

  const response = await fetch(
    `${apiBase}/api/documents/review-queue/${encodeURIComponent(reviewId)}/action`,
    {
      method: 'POST',
      credentials: 'include',
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

  return parseReviewActionResult(await response.json(), action)
}

export async function reviewDocumentById(
  documentId: string,
  action: 'approve' | 'reject',
  note?: string,
): Promise<{ id: string | null; status: string; extraction_status: string; document_id: string }> {
  const form = new FormData()
  form.append('action', action)
  if (note) form.append('note', note)

  const response = await fetch(
    `${apiBase}/api/documents/${encodeURIComponent(documentId)}/review`,
    {
      method: 'POST',
      credentials: 'include',
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

  const result: unknown = await response.json()
  if (
    !isRecord(result)
    || (result.id !== null && !isString(result.id))
    || !isString(result.status)
    || !isExtractionStatus(result.extraction_status)
    || result.extraction_status !== (action === 'approve' ? 'approved' : 'rejected')
    || !isString(result.document_id)
  ) {
    throw new Error('Server returned an invalid document review response.')
  }
  return {
    id: result.id,
    status: result.status,
    extraction_status: result.extraction_status,
    document_id: result.document_id,
  }
}

export function documentDownloadUrl(documentId: string): string {
  return `${apiBase}/api/documents/${encodeURIComponent(documentId)}/download`
}

export async function downloadDocumentFile(documentId: string, fileName: string): Promise<void> {
  const response = await fetch(documentDownloadUrl(documentId), {
    credentials: 'include',
  })
  if (!response.ok) throw new Error(`Download failed (${response.status})`)

  const blobUrl = URL.createObjectURL(await response.blob())
  const anchor = window.document.createElement('a')
  anchor.href = blobUrl
  anchor.download = fileName
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  // Let the browser consume the object URL before revoking it. Synchronous
  // revocation can cancel the download in browsers that schedule the anchor
  // navigation after the click handler returns.
  window.setTimeout(() => URL.revokeObjectURL(blobUrl), 0)
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

function parseCvPreview(value: unknown): CvPreview {
  if (!isRecord(value)) throw new Error('Server returned an invalid CV preview response.')
  const stringFields = ['full_name', 'email', 'phone', 'nationality', 'country_of_residence', 'date_of_birth', 'gender', 'flying_point'] as const
  for (const field of stringFields) {
    if (value[field] !== undefined && value[field] !== null && !isString(value[field])) {
      throw new Error('Server returned an invalid CV preview response.')
    }
  }
  const optionalString = (field: typeof stringFields[number]): string | null | undefined => {
    const fieldValue = value[field]
    return typeof fieldValue === 'string' || fieldValue === null ? fieldValue : undefined
  }
  const languages = value.languages
  if (
    languages !== undefined
    && languages !== null
    && !isString(languages)
    && !(Array.isArray(languages) && languages.every(isString))
  ) {
    throw new Error('Server returned an invalid CV preview response.')
  }
  const parsedLanguages = typeof languages === 'string' || languages === null
    ? languages
    : Array.isArray(languages)
      ? languages.filter(isString)
      : undefined
  return {
    full_name: optionalString('full_name'),
    email: optionalString('email'),
    phone: optionalString('phone'),
    nationality: optionalString('nationality'),
    country_of_residence: optionalString('country_of_residence'),
    date_of_birth: optionalString('date_of_birth'),
    gender: optionalString('gender'),
    languages: parsedLanguages,
    flying_point: optionalString('flying_point'),
  }
}

export async function previewCv(file: File): Promise<CvPreview> {
  const form = new FormData()
  form.append('file', file)
  const resp = await fetch(`${apiBase}/api/documents/preview-cv`, {
    method: 'POST',
    credentials: 'include',
    body: form,
  })
  if (!resp.ok) {
    const detail = await resp.json().catch(() => ({}))
    throw new Error(detail?.detail || `Could not read CV (${resp.status})`)
  }
  return parseCvPreview(await resp.json())
}

export async function uploadDocument(
  crewId: string,
  file: File,
  classification?: string,
  idempotencyKey?: string,
  issueDate?: string,
  expiryDate?: string,
  notes?: string,
  title?: string,
): Promise<UploadResult> {
  const form = new FormData()
  form.append('crew_id', crewId)
  form.append('file', file)
  if (classification) form.append('classification', classification)
  if (idempotencyKey) form.append('idempotency_key', idempotencyKey)
  if (issueDate) form.append('issue_date', issueDate)
  if (expiryDate) form.append('expiry_date', expiryDate)
  if (notes) form.append('notes', notes)
  if (title) form.append('title', title)

  const resp = await fetch(`${apiBase}/api/documents/upload`, {
    method: 'POST',
    credentials: 'include',
    body: form,
  })

  if (!resp.ok) {
    const detail = await resp.json().catch(() => ({}))
    throw new Error(detail?.detail || `Upload failed (${resp.status})`)
  }

  const rawResult: unknown = await resp.json()
  if (
    !isRecord(rawResult)
    || typeof rawResult.id !== 'string'
    || typeof rawResult.file_name !== 'string'
    || typeof rawResult.file_type !== 'string'
    || typeof rawResult.file_size !== 'number'
    || !Number.isFinite(rawResult.file_size)
    || !isExtractionStatus(rawResult.status)
  ) {
    throw new Error('Server returned an invalid upload response.')
  }
  const result: UploadResult = {
    id: rawResult.id,
    file_name: rawResult.file_name,
    file_type: rawResult.file_type,
    file_size: rawResult.file_size,
    status: rawResult.status,
  }
  if (result.status === 'failed') {
    throw new Error('Document received, but processing could not start. Please try again.')
  }
  return result
}

export async function getDocumentStatus(
  documentId: string
): Promise<{ id: string; file_name: string; extraction_status: string; classification?: string | null }> {
  const resp = await fetch(`${apiBase}/api/documents/${encodeURIComponent(documentId)}/status`, {
    credentials: 'include',
  })
  if (!resp.ok) {
    throw new Error(`Status check failed (${resp.status})`)
  }
  const result: unknown = await resp.json()
  if (
    !isRecord(result)
    || !isString(result.id)
    || !isString(result.file_name)
    || !isExtractionStatus(result.extraction_status)
    || (result.classification !== undefined && result.classification !== null && !isString(result.classification))
  ) {
    throw new Error('Server returned an invalid document status response.')
  }
  const classification = result.classification
  return {
    id: result.id,
    file_name: result.file_name,
    extraction_status: result.extraction_status,
    classification: typeof classification === 'string' || classification === null ? classification : undefined,
  }
}

export async function deleteDocument(documentId: string): Promise<void> {
  const resp = await fetch(`${apiBase}/api/documents/${encodeURIComponent(documentId)}`, {
    method: 'DELETE',
    credentials: 'include',
  })
  if (!resp.ok) {
    const detail = await resp.json().catch(() => ({}))
    throw new Error(detail?.detail || `Delete failed (${resp.status})`)
  }
}
