import { getAuthToken } from './apollo'
import { GRAPHQL_URL } from '../config'

const apiBase = GRAPHQL_URL.replace(/\/graphql\/?$/, '')

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
  classification?: string
): Promise<UploadResult> {
  const token = getAuthToken()
  const form = new FormData()
  form.append('crew_id', crewId)
  form.append('file', file)
  if (classification) form.append('classification', classification)

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
