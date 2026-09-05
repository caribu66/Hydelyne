import { useState, useCallback } from 'react';
import { useLazyQuery } from '@apollo/client';
import { SpecialistDocument, DocumentCategory } from '../types';
import { DOCUMENTS_BY_CREW_QUERY } from '../lib/queries';
import { deleteDocument, reviewDocumentById } from '../lib/documentsApi';

export function getDocumentComplianceStatus(doc: SpecialistDocument): {
  status: 'valid' | 'expiring_soon' | 'expired' | 'no_expiry';
  daysLeft?: number;
  label: string;
  badgeClass: string;
} {
  if (!doc.expiryDate) {
    return {
      status: 'no_expiry',
      label: 'Verified Permanent',
      badgeClass: 'bg-surface-raised text-secondary border-border-strong',
    };
  }

  const now = new Date();
  const expiry = new Date(doc.expiryDate);
  const diffTime = expiry.getTime() - now.getTime();
  const daysLeft = Math.ceil(diffTime / (1000 * 60 * 60 * 24));

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
    label: `Valid (${Math.floor(daysLeft / 30)} mo remaining)`,
    badgeClass: 'bg-positive/10 text-positive border-positive-border/20',
  };
}

export function useSpecialistDocuments() {
  const [documentsByProfile, setDocumentsByProfile] = useState<Record<string, SpecialistDocument[]>>({});
  const [fetchDocuments] = useLazyQuery(DOCUMENTS_BY_CREW_QUERY, { fetchPolicy: 'network-only' });

  const refreshDocuments = useCallback(async (profileId: string) => {
    const { data } = await fetchDocuments({ variables: { crewId: profileId } });
    const documents = (data?.documentsByCrew ?? []).map((doc: {
      id: string; fileName: string; fileSize: number; classification?: string | null;
      extractionStatus: string; uploadedAt: string;
      extractedText?: string | null; extractedData?: string | null; extractionConfidence?: string | null;
    }): SpecialistDocument => ({
      id: doc.id,
      title: doc.fileName.replace(/\.[^/.]+$/, '').replace(/[-_]/g, ' '),
      category: backendCategoryToFrontend(doc.classification),
      fileName: doc.fileName,
      fileSize: formatFileSize(doc.fileSize),
      uploadedAt: doc.uploadedAt,
      // A document is a verified credential when approved by a reviewer
      isVerified: doc.extractionStatus === 'approved',
      notes: `Extraction status: ${doc.extractionStatus}`,
      extractionStatus: doc.extractionStatus,
      extractedText: doc.extractedText || undefined,
      extractedData: safeJsonParse(doc.extractedData),
      extractionConfidence: safeJsonParse(doc.extractionConfidence),
    }));
    setDocumentsByProfile((current) => ({ ...current, [profileId]: documents }));
  }, [fetchDocuments]);

  const getDocumentsForProfile = useCallback((profileId: string): SpecialistDocument[] => {
    return documentsByProfile[profileId] || [];
  }, [documentsByProfile]);

  const removeDocument = useCallback(async (profileId: string, documentId: string) => {
    await deleteDocument(documentId);
    await refreshDocuments(profileId);
  }, [refreshDocuments]);

  const reviewDocument = useCallback(
    async (profileId: string, documentId: string, action: 'approve' | 'reject', note?: string) => {
      await reviewDocumentById(documentId, action, note);
      await refreshDocuments(profileId);
    },
    [refreshDocuments],
  );

  return {
    getDocumentsForProfile,
    removeDocument,
    reviewDocument,
    refreshDocuments,
  };
}

function backendCategoryToFrontend(category?: string | null): DocumentCategory {
  if (category === 'cv') return 'cv';
  if (category === 'cert') return 'certificate';
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
