import { useState, useCallback, useEffect, useRef } from 'react';
import { useLazyQuery } from '@apollo/client';
import { SpecialistDocument, DocumentCategory } from '../types';
import { DOCUMENTS_BY_CREW_QUERY } from '../lib/queries';
import { deleteDocument, reviewDocumentById } from '../lib/documentsApi';
import { apolloResultHasErrors, isSessionScopeCurrent } from '../utils/sessionScope';

export interface DocumentMutationResult {
  refreshFailed: boolean;
}

export async function refreshAfterDocumentMutation(
  refresh: () => Promise<void>,
): Promise<DocumentMutationResult> {
  try {
    await refresh();
    return { refreshFailed: false };
  } catch {
    return { refreshFailed: true };
  }
}

export function getDocumentComplianceStatus(doc: SpecialistDocument): {
  status: 'valid' | 'expiring_soon' | 'expired' | 'no_expiry' | 'invalid';
  daysLeft?: number;
  label: string;
  badgeClass: string;
} {
  if (doc.extractionStatus === 'rejected') {
    return {
      status: 'invalid',
      label: 'Rejected document',
      badgeClass: 'bg-danger-soft text-danger border-danger-border',
    };
  }

  if (!doc.expiryDate) {
    return {
      status: 'no_expiry',
      label: 'No expiry recorded',
      badgeClass: 'bg-surface-raised text-secondary border-border-strong',
    };
  }

  const now = new Date();
  const dateOnlyMatch = /^(\d{4})-(\d{2})-(\d{2})$/.exec(doc.expiryDate);
  const isDateOnly = dateOnlyMatch !== null;
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  let expiry: Date;
  if (dateOnlyMatch) {
    const year = Number(dateOnlyMatch[1]);
    const month = Number(dateOnlyMatch[2]);
    const day = Number(dateOnlyMatch[3]);
    expiry = new Date(year, month - 1, day);
    if (
      expiry.getFullYear() !== year
      || expiry.getMonth() !== month - 1
      || expiry.getDate() !== day
    ) {
      return {
        status: 'invalid',
        label: 'Invalid expiry date',
        badgeClass: 'bg-warning/10 text-warning border-warning-border/20',
      };
    }
  } else {
    expiry = new Date(doc.expiryDate);
  }
  if (Number.isNaN(expiry.getTime())) {
    return {
      status: 'invalid',
      label: 'Invalid expiry date',
      badgeClass: 'bg-warning/10 text-warning border-warning-border/20',
    };
  }
  const comparisonStart = isDateOnly ? today : now;
  const diffTime = expiry.getTime() - comparisonStart.getTime();
  const daysLeft = isDateOnly
    ? Math.round(diffTime / (1000 * 60 * 60 * 24))
    : Math.ceil(diffTime / (1000 * 60 * 60 * 24));

  if (daysLeft < 0) {
    return {
      status: 'expired',
      daysLeft,
      label: `Expired (${Math.abs(daysLeft)}d ago)`,
      badgeClass: 'bg-danger/10 text-danger border-danger-border/20',
    };
  }

  if (daysLeft <= 90) {
    return {
      status: 'expiring_soon',
      daysLeft,
      label: `Expiring Soon (${daysLeft}d left)`,
      badgeClass: 'bg-warning/10 text-warning border-warning-border/20',
    };
  }

  return {
    status: 'valid',
    daysLeft,
    label: doc.isVerified
      ? `Valid (${Math.floor(daysLeft / 30)} mo remaining)`
      : `Expiry recorded (${Math.floor(daysLeft / 30)} mo remaining)`,
    badgeClass: 'bg-positive/10 text-positive border-positive-border/20',
  };
}

export function useSpecialistDocuments(enabled = true, sessionKey: string | null = null) {
  const [documentsByProfile, setDocumentsByProfile] = useState<Record<string, SpecialistDocument[]>>({});
  const [fetchDocuments] = useLazyQuery(DOCUMENTS_BY_CREW_QUERY, { fetchPolicy: 'network-only' });
  const sessionEpochRef = useRef(0);
  const requestVersionByProfileRef = useRef<Record<string, number>>({});
  const [loadedSessionKey, setLoadedSessionKey] = useState<string | null>(null);
  const currentSessionKeyRef = useRef(sessionKey);
  const currentEnabledRef = useRef(enabled);
  currentSessionKeyRef.current = sessionKey;
  currentEnabledRef.current = enabled;

  useEffect(() => {
    sessionEpochRef.current += 1;
    setDocumentsByProfile({});
    setLoadedSessionKey(sessionKey);
  }, [enabled, sessionKey]);

  const refreshDocuments = useCallback(async (profileId: string) => {
    if (
      !isSessionScopeCurrent(enabled, loadedSessionKey, sessionKey) ||
      !currentEnabledRef.current ||
      currentSessionKeyRef.current !== sessionKey
    ) return;
    const requestEpoch = sessionEpochRef.current;
    const requestVersion = (requestVersionByProfileRef.current[profileId] ?? 0) + 1;
    requestVersionByProfileRef.current[profileId] = requestVersion;
    // A refresh is authoritative for this profile. Do not keep rendering a
    // deleted or no-longer-authorized document set while the replacement
    // request is pending or after it fails.
    setDocumentsByProfile((current) => {
      if (!(profileId in current)) return current;
      const next = { ...current };
      delete next[profileId];
      return next;
    });
    const result = await fetchDocuments({ variables: { crewId: profileId } });
    if (apolloResultHasErrors(result)) throw new Error('Document refresh failed');
    const { data } = result;
    if (
      !enabled ||
      !currentEnabledRef.current ||
      currentSessionKeyRef.current !== sessionKey ||
      requestEpoch !== sessionEpochRef.current ||
      requestVersion !== requestVersionByProfileRef.current[profileId]
    ) return;
    const documents = (data?.documentsByCrew ?? []).map((doc: {
      id: string; fileName: string; title?: string | null; fileSize: number; classification?: string | null;
      issueDate?: string | null; expiryDate?: string | null; notes?: string | null;
      extractionStatus: string; uploadedAt: string;
      extractedText?: string | null; extractedData?: string | null; extractionConfidence?: string | null;
    }): SpecialistDocument => ({
      id: doc.id,
      title: doc.title || doc.fileName.replace(/\.[^/.]+$/, '').replace(/[-_]/g, ' '),
      category: backendCategoryToFrontend(doc.classification),
      fileName: doc.fileName,
      fileSize: formatFileSize(doc.fileSize),
      uploadedAt: doc.uploadedAt,
      issueDate: doc.issueDate || undefined,
      expiryDate: doc.expiryDate || undefined,
      // A document is a verified credential when approved by a reviewer
      isVerified: doc.extractionStatus === 'approved',
      notes: [doc.notes, `Extraction status: ${doc.extractionStatus}`].filter(Boolean).join(' · '),
      extractionStatus: doc.extractionStatus,
      extractedText: doc.extractedText || undefined,
      extractedData: safeJsonParse(doc.extractedData),
      extractionConfidence: safeJsonParse(doc.extractionConfidence),
    }));
    setDocumentsByProfile((current) => ({ ...current, [profileId]: documents }));
  }, [enabled, fetchDocuments, loadedSessionKey, sessionKey]);

  const getDocumentsForProfile = useCallback((profileId: string): SpecialistDocument[] => {
    if (!isSessionScopeCurrent(enabled, loadedSessionKey, sessionKey)) return [];
    return documentsByProfile[profileId] || [];
  }, [documentsByProfile, enabled, loadedSessionKey, sessionKey]);

  const removeDocument = useCallback(async (profileId: string, documentId: string) => {
    if (
      !enabled ||
      !currentEnabledRef.current ||
      currentSessionKeyRef.current !== sessionKey
    ) return;
    await deleteDocument(documentId);
    if (!currentEnabledRef.current || currentSessionKeyRef.current !== sessionKey) return;
    return refreshAfterDocumentMutation(() => refreshDocuments(profileId));
  }, [enabled, refreshDocuments, sessionKey]);

  const reviewDocument = useCallback(
    async (profileId: string, documentId: string, action: 'approve' | 'reject', note?: string) => {
      if (
        !enabled ||
        !currentEnabledRef.current ||
        currentSessionKeyRef.current !== sessionKey
      ) return;
      await reviewDocumentById(documentId, action, note);
      if (!currentEnabledRef.current || currentSessionKeyRef.current !== sessionKey) return;
      return refreshAfterDocumentMutation(() => refreshDocuments(profileId));
    },
    [enabled, refreshDocuments, sessionKey],
  );

  return {
    getDocumentsForProfile,
    removeDocument,
    reviewDocument,
    refreshDocuments,
  };
}

export function backendCategoryToFrontend(category?: string | null): DocumentCategory {
  if (category === 'cv') return 'cv';
  if (category === 'cert' || category === 'certificate') return 'certificate';
  if (category === 'compliance') return 'medical';
  if (category === 'project') return 'survey_report';
  return 'other';
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function safeJsonParse(value?: string | null): Record<string, unknown> | undefined {
  if (!value) return undefined;
  try {
    const parsed = JSON.parse(value);
    return parsed && typeof parsed === 'object' ? parsed : undefined;
  } catch {
    return undefined;
  }
}
