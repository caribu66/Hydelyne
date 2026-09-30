import { SpecialistDocument } from '../types';

/** Returns true only when the original document binary is attached or hosted. */
export function hasOriginalDocumentFile(document: SpecialistDocument): boolean {
  const fileUrl = document.fileUrl;
  if (!fileUrl) return false;
  if (/^https?:\/\//i.test(fileUrl)) return true;
  // Data URLs are legitimate locally attached binaries (see types.ts), but a
  // bare `data:` allowlist also trusts `data:text/html` payloads from
  // untrusted index contents. Only accept inert document/image MIME types.
  const dataUrlMatch = /^data:([^;,]+)[;,]/i.exec(fileUrl);
  if (!dataUrlMatch?.[1]) return false;
  const mimeType = dataUrlMatch[1].trim().toLowerCase();
  return (
    mimeType === 'application/pdf' ||
    mimeType === 'application/octet-stream' ||
    mimeType === 'text/plain' ||
    mimeType.startsWith('image/')
  );
}

/** Review actions are valid only for non-terminal extraction states. */
export function isDocumentReviewable(extractionStatus?: string): boolean {
  return extractionStatus !== 'approved' && extractionStatus !== 'rejected';
}

/** Approval is valid only after extraction has produced reviewable evidence. */
export function isDocumentApprovalReady(extractionStatus?: string): boolean {
  return extractionStatus === 'extracted' || extractionStatus === 'needs_review';
}

/** Matches the document fields agents use to identify a record at a glance. */
export function documentMatchesQuery(document: SpecialistDocument, query: string): boolean {
  const normalizedQuery = query.trim().toLocaleLowerCase();
  if (!normalizedQuery) return true;

  return [document.title, document.fileName, document.notes]
    .filter((value): value is string => Boolean(value))
    .some((value) => value.toLocaleLowerCase().includes(normalizedQuery));
}
