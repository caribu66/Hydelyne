import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import {
  publicDocumentRequest,
  uploadRequestedDocument,
  uploadDocument,
  downloadDocumentFile,
  getDocumentStatus,
  deleteDocument,
  incomingDocumentReviews,
  previewCv,
} from './documentsApi'

describe('documentsApi contractor upload functions', () => {
  const originalFetch = globalThis.fetch

  beforeEach(() => {
    vi.resetAllMocks()
  })

  afterEach(() => {
    globalThis.fetch = originalFetch
    vi.unstubAllGlobals()
  })

  describe('publicDocumentRequest', () => {
  it('returns status and expires_at on valid token', async () => {
      globalThis.fetch = vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ status: 'active', expires_at: '2026-09-19T18:00:00Z' }),
      })

      const res = await publicDocumentRequest('valid-token-123')
      expect(res).toEqual({ status: 'active', expires_at: '2026-09-19T18:00:00Z' })
      expect(globalThis.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/documents/request/valid-token-123'),
      )
    })

    it('throws error when upload link is invalid or expired', async () => {
      globalThis.fetch = vi.fn().mockResolvedValue({
        ok: false,
        status: 404,
        json: async () => ({ detail: 'This upload link is invalid or has expired' }),
      })

      await expect(publicDocumentRequest('expired-token')).rejects.toThrow(
        'This upload link is invalid or has expired.',
      )
    })

    it('rejects an invalid success payload', async () => {
      globalThis.fetch = vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ status: 'active', expires_at: 'not-a-date' }),
      })

      await expect(publicDocumentRequest('malformed-token')).rejects.toThrow(
        'This upload link is invalid or has expired.',
      )
    })
  })

  describe('uploadRequestedDocument', () => {
    it('submits file with idempotency key and classification', async () => {
      const mockResult = { id: 'doc-99', file_name: 'test.pdf', status: 'pending' }
      globalThis.fetch = vi.fn().mockResolvedValue({
        ok: true,
        json: async () => mockResult,
      })

      const dummyFile = new File(['content'], 'test.pdf', { type: 'application/pdf' })
      const res = await uploadRequestedDocument('token-abc', dummyFile, 'idem-key-1', 'cert')

      expect(res).toEqual(mockResult)
      expect(globalThis.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/documents/request/token-abc/upload'),
        expect.objectContaining({
          method: 'POST',
          body: expect.any(FormData),
        }),
      )
    })

    it('surfaces backend error message on failure', async () => {
      globalThis.fetch = vi.fn().mockResolvedValue({
        ok: false,
        status: 400,
        json: async () => ({ detail: 'Invalid document category' }),
      })

      const dummyFile = new File(['content'], 'test.pdf', { type: 'application/pdf' })
      await expect(
        uploadRequestedDocument('token-abc', dummyFile, 'idem-key-1', 'invalid-cat'),
      ).rejects.toThrow('Invalid document category')
    })

    it('does not report a dispatch failure as a completed upload', async () => {
      globalThis.fetch = vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ id: 'doc-100', file_name: 'test.pdf', status: 'failed' }),
      })

      const dummyFile = new File(['content'], 'test.pdf', { type: 'application/pdf' })
      await expect(
        uploadRequestedDocument('token-abc', dummyFile, 'idem-key-2', 'cert'),
      ).rejects.toThrow('Document received, but processing could not start')
    })

    it('rejects an incomplete success response', async () => {
      globalThis.fetch = vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ status: 'pending' }),
      })

      const dummyFile = new File(['content'], 'test.pdf', { type: 'application/pdf' })
      await expect(
        uploadRequestedDocument('token-abc', dummyFile, 'idem-key-3', 'cert'),
      ).rejects.toThrow('invalid upload response')
    })

    it('rejects an impossible extraction status', async () => {
      globalThis.fetch = vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ id: 'doc-101', file_name: 'test.pdf', status: 'complete-ish' }),
      })

      const dummyFile = new File(['content'], 'test.pdf', { type: 'application/pdf' })
      await expect(
        uploadRequestedDocument('token-abc', dummyFile, 'idem-key-4', 'cert'),
      ).rejects.toThrow('invalid upload response')
    })
  })

  describe('uploadDocument', () => {
    it('sends the caller-provided idempotency key', async () => {
      globalThis.fetch = vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          id: 'doc-102',
          file_name: 'test.pdf',
          file_type: 'pdf',
          file_size: 7,
          status: 'pending',
        }),
      })

      const dummyFile = new File(['content'], 'test.pdf', { type: 'application/pdf' })
      await uploadDocument('crew-1', dummyFile, 'cert', 'modal-upload-key')

      const request = vi.mocked(globalThis.fetch).mock.calls[0]?.[1]
      expect(request?.body).toBeInstanceOf(FormData)
      expect((request?.body as FormData).get('idempotency_key')).toBe('modal-upload-key')
    })

    it('does not report a dispatch failure as a completed upload', async () => {
      globalThis.fetch = vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          id: 'doc-101',
          file_name: 'test.pdf',
          file_type: 'pdf',
          file_size: 7,
          status: 'failed',
        }),
      })

      const dummyFile = new File(['content'], 'test.pdf', { type: 'application/pdf' })
      await expect(uploadDocument('crew-1', dummyFile, 'cert')).rejects.toThrow(
        'Document received, but processing could not start',
      )
    })

    it('rejects an incomplete success response', async () => {
      globalThis.fetch = vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ status: 'pending' }),
      })

      const dummyFile = new File(['content'], 'test.pdf', { type: 'application/pdf' })
      await expect(uploadDocument('crew-1', dummyFile, 'cert')).rejects.toThrow(
        'invalid upload response',
      )
    })
  })

  describe('actionIncomingDocumentReview', () => {
    it('rejects a non-terminal status from an approve response', async () => {
      globalThis.fetch = vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ id: 'review-1', status: 'claimed', document_id: 'doc-1' }),
      })

      const { actionIncomingDocumentReview } = await import('./documentsApi')
      await expect(actionIncomingDocumentReview('review-1', 'approve')).rejects.toThrow(
        'invalid document review response',
      )
    })
  })

  describe('reviewDocumentById', () => {
    it('rejects an approve response that is not approved', async () => {
      globalThis.fetch = vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          id: 'review-1',
          status: 'resolved',
          extraction_status: 'needs_review',
          document_id: 'doc-1',
        }),
      })

      const { reviewDocumentById } = await import('./documentsApi')
      await expect(reviewDocumentById('doc-1', 'approve')).rejects.toThrow(
        'invalid document review response',
      )
    })
  })

  describe('downloadDocumentFile', () => {
    it('uses the HttpOnly session cookie without a bearer token', async () => {
      const storage = new Map<string, string>([['hydenlyne_token', 'stale-account-token']])
      vi.stubGlobal('localStorage', {
        getItem: (key: string) => storage.get(key) ?? null,
        removeItem: (key: string) => storage.delete(key),
      })
      vi.stubGlobal('sessionStorage', {
        getItem: (key: string) => storage.get(key) ?? null,
        removeItem: (key: string) => storage.delete(key),
      })
      globalThis.fetch = vi.fn().mockResolvedValue({ ok: false, status: 401 })

      await expect(downloadDocumentFile('doc-1', 'original.pdf')).rejects.toThrow('Download failed (401)')
      expect(globalThis.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/documents/doc-1/download'),
        expect.objectContaining({
          credentials: 'include',
        }),
      )
    })

    it('defers object URL revocation until after the download is triggered', async () => {
      const revoke = vi.fn()
      const callbacks: Array<() => void> = []
      const delays: Array<number> = []
      const anchor = {
        href: '',
        download: '',
        click: vi.fn(),
        remove: vi.fn(),
      }
      vi.stubGlobal('URL', {
        createObjectURL: vi.fn().mockReturnValue('blob:document-1'),
        revokeObjectURL: revoke,
      })
      const documentStub = {
        createElement: vi.fn().mockReturnValue(anchor),
        body: { appendChild: vi.fn() },
      }
      vi.stubGlobal('document', documentStub)
      vi.stubGlobal('window', {
        document: documentStub,
        setTimeout: (callback: () => void, delay?: number) => {
          callbacks.push(callback)
          delays.push(delay ?? 0)
          return 1
        },
      })
      globalThis.fetch = vi.fn().mockResolvedValue({
        ok: true,
        blob: async () => new Blob(['document']),
      })

      await downloadDocumentFile('doc-1', 'original.pdf')

      expect(anchor.click).toHaveBeenCalledOnce()
      expect(revoke).not.toHaveBeenCalled()
      // The grace period keeps the URL alive for browsers that consume the
      // anchor navigation asynchronously (Firefox/Safari).
      expect(delays[0]).toBeGreaterThanOrEqual(1000)
      const revokeCallback = callbacks[0]
      expect(revokeCallback).toBeDefined()
      revokeCallback?.()
      expect(revoke).toHaveBeenCalledWith('blob:document-1')
    })
  })

  it('encodes document IDs in status and delete paths', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ id: 'doc', file_name: 'file.pdf', extraction_status: 'extracted' }),
    })

    await getDocumentStatus('doc/with unsafe path')
    await deleteDocument('doc/with unsafe path')

    expect(globalThis.fetch).toHaveBeenNthCalledWith(
      1,
      expect.stringContaining('/api/documents/doc%2Fwith%20unsafe%20path/status'),
      expect.any(Object),
    )
    expect(globalThis.fetch).toHaveBeenNthCalledWith(
      2,
      expect.stringContaining('/api/documents/doc%2Fwith%20unsafe%20path'),
      expect.objectContaining({ method: 'DELETE' }),
    )
  })

  it('rejects malformed document status responses', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ id: 'doc-1', extraction_status: 'pending' }),
    })

    await expect(getDocumentStatus('doc-1')).rejects.toThrow('invalid document status response')
  })

  it('rejects malformed review queue responses', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ reviews: [] }),
    })

    await expect(incomingDocumentReviews()).rejects.toThrow('invalid document review queue')
  })

  it('rejects malformed CV preview responses', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ full_name: { value: 'Unexpected object' } }),
    })

    const file = new File(['cv'], 'candidate.pdf', { type: 'application/pdf' })
    await expect(previewCv(file)).rejects.toThrow('invalid CV preview response')
  })
})
