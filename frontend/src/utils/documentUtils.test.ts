import { describe, expect, it } from 'vitest';
import { SpecialistDocument } from '../types';
import {
  documentMatchesQuery,
  hasOriginalDocumentFile,
  isDocumentApprovalReady,
  isDocumentReviewable,
} from './documentUtils';

const document: SpecialistDocument = {
  id: 'document-1',
  title: 'BOSIET Certificate',
  category: 'certificate',
  fileName: 'BOSIET_2026.pdf',
  notes: 'Verified for North Sea mobilisation',
  uploadedAt: '2026-09-01T08:00:00.000Z',
};

describe('documentMatchesQuery', () => {
  it.each(['bosiet', '2026.pdf', 'north sea', '  mobilisation  '])(
    'matches a document by an agent-facing field: %s',
    (query) => {
      expect(documentMatchesQuery(document, query)).toBe(true);
    },
  );

  it('does not match unrelated text', () => {
    expect(documentMatchesQuery(document, 'passport')).toBe(false);
  });
});

describe('hasOriginalDocumentFile', () => {
  it('only accepts locally attached data or HTTP(S) files', () => {
    expect(hasOriginalDocumentFile({ ...document, fileUrl: 'https://documents.example/BOSIET.pdf' })).toBe(true);
    expect(hasOriginalDocumentFile({ ...document, fileUrl: 'file:///private/BOSIET.pdf' })).toBe(false);
    expect(hasOriginalDocumentFile({ ...document, fileUrl: 'javascript:alert(1)' })).toBe(false);
  });

  it('accepts inert data-URL document binaries', () => {
    expect(
      hasOriginalDocumentFile({ ...document, fileUrl: 'data:application/pdf;base64,JVBERi0x' }),
    ).toBe(true);
    expect(hasOriginalDocumentFile({ ...document, fileUrl: 'data:image/png;base64,iVBOR' })).toBe(true);
  });

  it('rejects active data-URL payloads from untrusted index contents', () => {
    expect(
      hasOriginalDocumentFile({ ...document, fileUrl: 'data:text/html,<script>alert(1)</script>' }),
    ).toBe(false);
    expect(
      hasOriginalDocumentFile({ ...document, fileUrl: 'data:application/xhtml+xml;base64,PGI+' }),
    ).toBe(false);
    expect(
      hasOriginalDocumentFile({ ...document, fileUrl: 'data:application/javascript;base64,YWxlcnQ=' }),
    ).toBe(false);
  });
});

describe('isDocumentReviewable', () => {
  it('rejects terminal review states that the backend cannot change', () => {
    expect(isDocumentReviewable('approved')).toBe(false);
    expect(isDocumentReviewable('rejected')).toBe(false);
    expect(isDocumentReviewable('needs_review')).toBe(true);
    expect(isDocumentReviewable('pending')).toBe(true);
  });
});

describe('isDocumentApprovalReady', () => {
  it('matches the backend states that may be approved', () => {
    expect(isDocumentApprovalReady('extracted')).toBe(true);
    expect(isDocumentApprovalReady('needs_review')).toBe(true);
    expect(isDocumentApprovalReady('pending')).toBe(false);
    expect(isDocumentApprovalReady('processing')).toBe(false);
    expect(isDocumentApprovalReady('failed')).toBe(false);
  });
});
