import { SpecialistDocument } from '../types';

/** Returns true only when the original document binary is attached or hosted. */
export function hasOriginalDocumentFile(document: SpecialistDocument): boolean {
  return Boolean(document.fileUrl && /^(data:|https?:\/\/)/i.test(document.fileUrl));
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
