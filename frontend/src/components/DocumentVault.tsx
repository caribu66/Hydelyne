import { FC, useEffect, useMemo, useRef, useState, MouseEvent } from 'react';
import { UserProfile, SpecialistDocument, DocumentCategory } from '../types';
import { getDocumentComplianceStatus } from '../hooks/useSpecialistDocuments';
import type { DocumentMutationResult } from '../hooks/useSpecialistDocuments';
import {
  documentTimestamp,
  formatDocumentDate,
  formatDocumentDateTime,
  isDocumentAuditCleared,
  resolveSelectedDocument,
} from './documentVaultUtils';
import { DocumentPreviewModal } from './DocumentPreviewModal';
import { DocumentUploadModal } from './DocumentUploadModal';
import { documentMatchesQuery, hasOriginalDocumentFile } from '../utils/documentUtils';
import { createDocumentRequest, downloadDocumentFile } from '../lib/documentsApi';
import {
  FileText,
  ShieldCheck,
  UploadCloud,
  Download,
  Eye,
  CheckCircle2,
  FileCheck,
  FileBadge,
  Activity,
  FolderArchive,
  ArrowUpDown,
  Clock,
  Sparkles,
  Search,
  Send,
  X,
} from 'lucide-react';

export type DocumentSortOption = 'uploaded-desc' | 'uploaded-asc' | 'expiry-asc' | 'title-asc';

interface DocumentVaultProps {
  profile: UserProfile;
  documents: SpecialistDocument[];
  onAddDocument: () => void | Promise<void>;
  onRemoveDocument: (docId: string) => void | Promise<void | DocumentMutationResult>;
  onReviewDocument?: (docId: string, action: 'approve' | 'reject') => void | Promise<void | DocumentMutationResult>;
  onShowToast: (msg: string) => void;
  canManageDocuments?: boolean;
  canRequestDocuments?: boolean;
  sessionKey?: string | null;
  compact?: boolean;
}

export const DocumentVault: FC<DocumentVaultProps> = ({
  profile,
  documents,
  onAddDocument,
  onRemoveDocument,
  onReviewDocument,
  onShowToast,
  canManageDocuments = false,
  canRequestDocuments = false,
  sessionKey = null,
  compact = false,
}) => {
  const [selectedDoc, setSelectedDoc] = useState<SpecialistDocument | null>(null);
  const [isUploadOpen, setIsUploadOpen] = useState(false);
  const [activeCategory, setActiveCategory] = useState<string>('all');
  const [sortOption, setSortOption] = useState<DocumentSortOption>('uploaded-desc');
  const [searchQuery, setSearchQuery] = useState('');
  const currentSessionKeyRef = useRef(sessionKey);
  currentSessionKeyRef.current = sessionKey;

  useEffect(() => {
    setSelectedDoc(null);
    setIsUploadOpen(false);
    setActiveCategory('all');
    setSortOption('uploaded-desc');
    setSearchQuery('');
  }, [profile.id, sessionKey]);

  useEffect(() => {
    setSelectedDoc((selected) => resolveSelectedDocument(selected, documents));
  }, [documents]);

  const handleRequestDocument = async () => {
    if (!sessionKey || currentSessionKeyRef.current !== sessionKey) return;
    try {
      const request = await createDocumentRequest(profile.id);
      if (currentSessionKeyRef.current !== sessionKey) return;
      const link = `${window.location.origin}/upload/${encodeURIComponent(request.token)}`;
      await navigator.clipboard.writeText(link);
      if (currentSessionKeyRef.current !== sessionKey) return;
      onShowToast('Secure upload link copied — it expires in 14 days');
    } catch (error) {
      if (currentSessionKeyRef.current !== sessionKey) return;
      onShowToast(error instanceof Error ? error.message : 'Could not create a secure upload link');
    }
  };

  // Compute metrics
  const totalCount = documents.length;
  const expiredCount = documents.filter((d) => getDocumentComplianceStatus(d).status === 'expired').length;
  const expiringSoonCount = documents.filter((d) => getDocumentComplianceStatus(d).status === 'expiring_soon').length;
  const invalidExpiryCount = documents.filter((d) => getDocumentComplianceStatus(d).status === 'invalid').length;
  const reviewRequiredCount = documents.filter((d) => !d.isVerified).length;
  const auditCleared = isDocumentAuditCleared(
    documents.map((document) => ({
      isVerified: document.isVerified,
      complianceStatus: getDocumentComplianceStatus(document).status,
    })),
  );

  // Auto-sort documents by upload date (newest first) by default
  const sortedAndFilteredDocs = useMemo(() => {
    return [...documents]
      .filter((doc) => {
        if (activeCategory !== 'all' && doc.category !== activeCategory) {
          return false;
        }
        return documentMatchesQuery(doc, searchQuery);
      })
      .sort((a, b) => {
        if (sortOption === 'uploaded-desc') {
          const timeA = documentTimestamp(a.uploadedAt) ?? documentTimestamp(a.issueDate) ?? 0;
          const timeB = documentTimestamp(b.uploadedAt) ?? documentTimestamp(b.issueDate) ?? 0;
          return timeB - timeA;
        }
        if (sortOption === 'uploaded-asc') {
          const timeA = documentTimestamp(a.uploadedAt) ?? documentTimestamp(a.issueDate) ?? 0;
          const timeB = documentTimestamp(b.uploadedAt) ?? documentTimestamp(b.issueDate) ?? 0;
          return timeA - timeB;
        }
        if (sortOption === 'expiry-asc') {
          const timeA = documentTimestamp(a.expiryDate);
          const timeB = documentTimestamp(b.expiryDate);
          if (timeA === null && timeB === null) return 0;
          if (timeA === null) return 1;
          if (timeB === null) return -1;
          return timeA - timeB;
        }
        if (sortOption === 'title-asc') {
          return a.title.localeCompare(b.title);
        }
        return 0;
      });
  }, [documents, activeCategory, searchQuery, sortOption]);

  const hasActiveFilters = activeCategory !== 'all' || Boolean(searchQuery.trim());
  const clearFilters = () => {
    setActiveCategory('all');
    setSearchQuery('');
  };

  const getCategoryIcon = (category: DocumentCategory) => {
    switch (category) {
      case 'medical':
        return Activity;
      case 'certificate':
        return FileBadge;
      case 'cv':
        return FileText;
      case 'seamans_book':
        return ShieldCheck;
      case 'survey_report':
        return FileCheck;
      default:
        return FileText;
    }
  };

  const handleDownloadSingle = async (doc: SpecialistDocument, e: MouseEvent) => {
    e.stopPropagation();
    if (!sessionKey || currentSessionKeyRef.current !== sessionKey) return;
    if (doc.fileUrl && hasOriginalDocumentFile(doc)) {
      const a = window.document.createElement('a');
      a.href = doc.fileUrl;
      a.download = doc.fileName || `${doc.title}.pdf`;
      window.document.body.appendChild(a);
      a.click();
      a.remove();
    } else if (canManageDocuments) {
      try {
        await downloadDocumentFile(doc.id, doc.fileName || `${doc.title}.pdf`);
        if (currentSessionKeyRef.current !== sessionKey) return;
      } catch (error) {
        if (currentSessionKeyRef.current !== sessionKey) return;
        onShowToast(error instanceof Error ? error.message : 'Could not download the original file');
        return;
      }
    } else {
      onShowToast(`Original file unavailable for “${doc.title}”. Export the compliance record instead.`);
      return;
    }
    if (currentSessionKeyRef.current === sessionKey) onShowToast(`Downloaded ${doc.fileName}`);
  };

  const handleDownloadAllBundle = () => {
    if (!sessionKey || currentSessionKeyRef.current !== sessionKey) return;
    const summary = documents
      .map((d, i) => {
        const compliance = getDocumentComplianceStatus(d);
        return `[${i + 1}] ${d.title}\nCategory: ${d.category.toUpperCase()} | File: ${d.fileName}\nUploaded: ${formatDocumentDateTime(d.uploadedAt)} | Validity: ${compliance.label} | Issued: ${d.issueDate || 'N/A'}\nNotes: ${d.notes || 'None'}\n`;
      })
      .join('\n----------------------------------------\n');

    const manifest = `HYDENLYNE COMPLIANCE BUNDLE MANIFEST
===================================================
CONTRACTOR: ${profile.name}
DISCIPLINE: ${profile.department} (${profile.title})
TOTAL CREDENTIALS: ${documents.length}
MOBILISATION COMPLIANCE: ${auditCleared ? '100% AUDIT COMPLIANT (CLEARED)' : 'ACTION REQUIRED'}
GENERATED AT: ${new Date().toLocaleString()}
===================================================

DOCUMENT REGISTRATION INVENTORY:
----------------------------------------
${summary}
===================================================
Documents listed above are recorded in the document vault for compliance review.`;

    const blob = new Blob([manifest], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = window.document.createElement('a');
    a.href = url;
    a.download = `${profile.name.replace(/\s+/g, '_')}_Compliance_Bundle.txt`;
    window.document.body.appendChild(a);
    a.click();
    window.document.body.removeChild(a);
    window.setTimeout(() => URL.revokeObjectURL(url), 0);
    onShowToast(`Exported complete compliance bundle for ${profile.name.split(' ')[0]}`);
  };

  return (
    <div className="space-y-3">
      {/* Compliance Header & Action Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2.5 bg-canvas/80 border border-border-subtle rounded-[10px] p-3">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-surface border border-border-strong flex items-center justify-center text-secondary shrink-0">
            <ShieldCheck className="w-4 h-4 text-secondary" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-xs font-bold text-primary">Compliance & Document Vault</span>
              <span className="px-1.5 py-0.2 rounded bg-surface-raised text-secondary font-mono text-xs">
                {totalCount} files
              </span>
            </div>
            <p className="text-xs text-secondary">
              {totalCount === 0 ? (
                <span className="text-secondary font-medium">No compliance documents recorded</span>
              ) : expiredCount > 0 ? (
                <span className="text-danger font-medium">⚠️ {expiredCount} document expired</span>
              ) : expiringSoonCount > 0 ? (
                <span className="text-warning font-medium">⚠️ {expiringSoonCount} document expiring soon</span>
              ) : invalidExpiryCount > 0 ? (
                <span className="text-warning font-medium">⚠️ {invalidExpiryCount} document{invalidExpiryCount === 1 ? '' : 's'} have an invalid expiry date</span>
              ) : reviewRequiredCount > 0 ? (
                <span className="text-warning font-medium">⚠️ {reviewRequiredCount} document{reviewRequiredCount === 1 ? '' : 's'} need{reviewRequiredCount === 1 ? 's' : ''} compliance review</span>
              ) : (
                <span className="text-positive font-medium">✓ All recorded documents verified and current</span>
              )}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2 self-end sm:self-center">
          {canRequestDocuments && <button
            type="button"
            onClick={() => void handleRequestDocument()}
            className="inline-flex min-h-11 items-center gap-1 rounded-lg border border-border-subtle bg-surface px-3 text-xs font-semibold text-secondary hover:bg-surface-raised hover:text-primary focus-visible:ring-2 focus-visible:ring-focus"
          >
            <Send className="h-3.5 w-3.5" />
            <span>Request documents</span>
          </button>}
          {totalCount > 0 && (
            <button
              type="button"
              onClick={handleDownloadAllBundle}
              className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg bg-surface-raised hover:bg-surface-selected text-secondary hover:text-primary text-xs font-medium transition-colors cursor-pointer"
              title="Download full compliance manifest"
            >
              <FolderArchive className="w-3.5 h-3.5" />
              <span className="hidden md:inline">Export Bundle</span>
            </button>
          )}

              {canManageDocuments && <button
                type="button"
                onClick={() => setIsUploadOpen(true)}
                aria-label={`Upload a document for ${profile.name}`}
            className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg bg-action hover:bg-action-hover text-on-action text-xs font-semibold transition-colors cursor-pointer shadow-xs"
          >
            <UploadCloud className="w-3.5 h-3.5" />
            <span>Upload Document</span>
          </button>}
        </div>
      </div>

      {/* Auto-Sort and Filter Toolbar */}
      {!compact && (
        <div className="space-y-2.5 bg-surface/50 border border-border-subtle/80 rounded-[10px] p-2.5">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <label className="relative block w-full sm:max-w-xs">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" aria-hidden="true" />
              <span className="sr-only">Search {profile.name}'s documents</span>
              <input
                type="search"
                value={searchQuery}
                onChange={(event) => setSearchQuery(event.target.value)}
                placeholder="Search documents"
                className="min-h-11 w-full rounded-[10px] border border-border-strong bg-canvas py-2 pl-9 pr-9 text-sm text-primary placeholder:text-muted focus:outline-hidden focus:ring-2 focus:ring-focus"
              />
              {searchQuery && (
                <button
                  type="button"
                  onClick={() => setSearchQuery('')}
                  aria-label="Clear document search"
                  className="absolute right-1 top-1/2 inline-flex min-h-9 min-w-9 -translate-y-1/2 items-center justify-center rounded-md text-secondary hover:bg-surface-raised hover:text-primary"
                >
                  <X className="h-4 w-4" aria-hidden="true" />
                </button>
              )}
            </label>

            <div className="flex items-center justify-between gap-2 text-xs text-secondary sm:justify-end">
              <span aria-live="polite" className="font-mono">
                Showing {sortedAndFilteredDocs.length} of {totalCount}
              </span>
              {hasActiveFilters && (
                <button
                  type="button"
                  onClick={clearFilters}
                  className="min-h-9 rounded-lg px-2 text-xs font-medium text-accent hover:bg-accent-soft/60 focus:outline-hidden focus:ring-2 focus:ring-focus"
                >
                  Clear filters
                </button>
              )}
            </div>
          </div>

          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2.5">
          {/* Category Pills Filter */}
          <div className="flex items-center gap-1.5 overflow-x-auto scrollbar-none py-0.5 text-xs">
            {[
              { id: 'all', label: 'All', count: totalCount },
              { id: 'certificate', label: 'Safety / Certs', count: documents.filter((d) => d.category === 'certificate').length },
              { id: 'medical', label: 'Medicals', count: documents.filter((d) => d.category === 'medical').length },
              { id: 'cv', label: 'CV & Track Record', count: documents.filter((d) => d.category === 'cv').length },
              { id: 'survey_report', label: 'Reports & Logs', count: documents.filter((d) => d.category === 'survey_report').length },
            ].map((cat) => (
              <button
                key={cat.id}
                type="button"
                onClick={() => setActiveCategory(cat.id)}
                aria-pressed={activeCategory === cat.id}
                className={`px-2.5 py-1 rounded-lg text-xs font-medium border transition-colors shrink-0 cursor-pointer ${
                  activeCategory === cat.id
                    ? 'bg-surface-raised text-primary border-border-strong font-semibold shadow-2xs'
                    : 'bg-canvas/60 text-secondary border-border-subtle hover:text-primary'
                }`}
              >
                {cat.label} {cat.count > 0 && <span className="opacity-70 font-mono text-xs">({cat.count})</span>}
              </button>
            ))}
          </div>

          {/* Auto-Sort Control Strip */}
          <div className="flex items-center gap-2 shrink-0 self-end sm:self-center">
            <div className="flex items-center gap-1.5 text-xs">
              <span className="text-secondary flex items-center gap-1 font-mono text-xs">
                <ArrowUpDown className="w-3 h-3 text-secondary" />
                <span className="hidden md:inline">Sort:</span>
              </span>
              <select
                id="document-sort-select"
                value={sortOption}
                onChange={(e) => setSortOption(e.target.value as DocumentSortOption)}
                className="bg-canvas border border-border-strong text-primary text-xs rounded-lg px-2.5 py-1 font-medium focus:outline-hidden focus:ring-1 focus:ring-focus cursor-pointer"
                title="Sort documents"
              >
                <option value="uploaded-desc">Auto-Sort: Upload Date (Newest first)</option>
                <option value="uploaded-asc">Upload Date (Oldest first)</option>
                <option value="expiry-asc">Expiry Date (Expiring soonest)</option>
                <option value="title-asc">Document Name (A–Z)</option>
              </select>
            </div>

            {sortOption === 'uploaded-desc' && (
              <span
                className="px-2 py-0.5 rounded-md bg-action/10 border border-border-strong/20 text-accent text-xs font-mono font-medium flex items-center gap-1"
                title="Auto-sort is actively organizing files newest upload first"
              >
                <Sparkles className="w-2.5 h-2.5" />
                <span>Auto-Sorted</span>
              </span>
            )}
          </div>
          </div>
        </div>
      )}

      {/* Document Grid / List */}
      {sortedAndFilteredDocs.length > 0 ? (
        <div className="grid grid-cols-1 gap-2">
          {sortedAndFilteredDocs.map((doc, idx) => {
            const compliance = getDocumentComplianceStatus(doc);
            const IconComponent = getCategoryIcon(doc.category);
            const isLatest = sortOption === 'uploaded-desc' && idx === 0;

            return (
              <div
                key={doc.id}
                onClick={() => setSelectedDoc(doc)}
                className="group p-3 rounded-[10px] bg-surface/60 hover:bg-surface border border-border-subtle hover:border-border-strong transition-all cursor-pointer flex items-center justify-between gap-3 shadow-xs"
              >
                <div className="flex items-center gap-3 min-w-0 flex-1">
                  <div className="w-9 h-9 rounded-lg bg-surface-raised/80 border border-border-strong/60 flex items-center justify-center text-secondary shrink-0 group-hover:border-border-strong transition-colors">
                    <IconComponent className="w-4 h-4" />
                  </div>

                  <div className="min-w-0 flex-1 space-y-0.5">
                    <div className="flex items-center gap-2">
                      <h4 className="text-xs font-semibold text-primary group-hover:text-primary transition-colors truncate">
                        {doc.title}
                      </h4>
                      {doc.isVerified && (
                        <span title="Verified Credential"><CheckCircle2 className="w-3.5 h-3.5 text-positive shrink-0" /></span>
                      )}
                      {doc.extractionStatus === 'rejected' && (
                        <span className="px-1.5 py-0.2 rounded bg-danger-soft/60 border border-danger-border text-danger font-mono text-xs font-semibold shrink-0">
                          Rejected
                        </span>
                      )}
                      {doc.extractionStatus && doc.extractionStatus !== 'approved' && doc.extractionStatus !== 'rejected' && (
                        <span className="px-1.5 py-0.2 rounded bg-warning-soft/70 border border-warning-border text-warning font-mono text-xs font-semibold shrink-0">
                          Needs Review
                        </span>
                      )}
                      {isLatest && (
                        <span className="px-1.5 py-0.2 rounded bg-surface-raised border border-border-strong text-secondary font-mono text-xs font-medium shrink-0">
                          Latest Upload
                        </span>
                      )}
                    </div>

                    <div className="flex items-center gap-2 text-xs text-secondary flex-wrap">
                      <span className="font-mono text-secondary">{doc.fileName}</span>
                      {doc.fileSize && <span>• {doc.fileSize}</span>}
                      <span>•</span>
                      <span className="flex items-center gap-1 font-mono text-secondary" title={`Uploaded: ${formatDocumentDateTime(doc.uploadedAt)}`}>
                        <Clock className="w-3 h-3 text-secondary" />
                        <span>Uploaded {formatDocumentDate(doc.uploadedAt)}</span>
                      </span>
                      <span>•</span>
                      <span className={`px-2 py-0.2 rounded text-xs font-semibold border ${compliance.badgeClass}`}>
                        {compliance.label}
                      </span>
                    </div>
                  </div>
                </div>

                {/* Right Action Icons */}
                <div className="flex items-center gap-1.5 shrink-0" onClick={(e) => e.stopPropagation()}>
                  <button
                    type="button"
                    onClick={(e) => handleDownloadSingle(doc, e)}
                    aria-label={`Download ${doc.title}`}
                    disabled={!hasOriginalDocumentFile(doc) && !canManageDocuments}
                    className="p-1.5 rounded-lg bg-surface-raised hover:bg-surface-selected text-secondary hover:text-primary transition-colors cursor-pointer disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:bg-surface-raised"
                    title={hasOriginalDocumentFile(doc) || canManageDocuments ? 'Download original file' : 'Original file unavailable; export the compliance record instead'}
                  >
                    <Download className="w-3.5 h-3.5" />
                  </button>

                  <button
                    type="button"
                    onClick={() => setSelectedDoc(doc)}
                    aria-label={`Preview ${doc.title}`}
                    className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg bg-surface-raised hover:bg-surface-selected text-secondary hover:text-primary font-medium text-xs transition-colors cursor-pointer border border-border-strong/60"
                  >
                    <Eye className="w-3.5 h-3.5" />
                    <span className="hidden sm:inline">Preview</span>
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <div className="text-center py-6 border border-dashed border-border-subtle rounded-[10px] bg-canvas/40 space-y-2">
          <FileText className="w-6 h-6 text-muted mx-auto" />
          <p className="text-sm font-medium text-secondary">
            {hasActiveFilters ? 'No documents match those filters.' : 'No documents recorded yet.'}
          </p>
          {hasActiveFilters && (
            <button
              type="button"
              onClick={clearFilters}
              className="min-h-11 rounded-lg px-3 text-xs font-semibold text-accent hover:bg-accent-soft/60 focus:outline-hidden focus:ring-2 focus:ring-focus"
            >
              Show all documents
            </button>
          )}
          {canManageDocuments && <button
            type="button"
            onClick={() => setIsUploadOpen(true)}
            className="text-xs text-accent hover:underline font-medium"
          >
            Upload first document
          </button>}
        </div>
      )}

      {/* Upload Modal */}
      {canManageDocuments && <DocumentUploadModal
        isOpen={isUploadOpen}
        onClose={() => setIsUploadOpen(false)}
        profile={profile}
        onAddDocument={onAddDocument}
        onShowToast={onShowToast}
        sessionKey={sessionKey}
      />}

      {/* Preview Modal */}
      <DocumentPreviewModal
        isOpen={Boolean(selectedDoc)}
        onClose={() => setSelectedDoc(null)}
        document={selectedDoc}
        profile={profile}
        onDelete={canManageDocuments ? (docId) => onRemoveDocument(docId) : undefined}
        onShowToast={onShowToast}
        onReviewAction={canManageDocuments ? onReviewDocument : undefined}
        canReview={canManageDocuments}
        canDownloadOriginal={canManageDocuments}
        sessionKey={sessionKey}
      />
    </div>
  );
};
