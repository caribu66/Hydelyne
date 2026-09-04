import { describe, expect, it } from 'vitest';
import { SpecialistDocument } from '../types';
import { documentMatchesQuery, hasOriginalDocumentFile } from './documentUtils';

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
  });
});
