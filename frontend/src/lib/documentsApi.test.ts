import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { publicDocumentRequest, uploadRequestedDocument } from './documentsApi'

describe('documentsApi contractor upload functions', () => {
  const originalFetch = globalThis.fetch

  beforeEach(() => {
    vi.resetAllMocks()
  })

  afterEach(() => {
    globalThis.fetch = originalFetch
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
  })
})
