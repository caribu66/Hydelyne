import { SpecialistDocument } from '../types';

/** Returns true only when the original document binary is attached or hosted. */
export function hasOriginalDocumentFile(document: SpecialistDocument): boolean {
  return Boolean(document.fileUrl && /^(data:|https?:\/\/)/i.test(document.fileUrl));
}
