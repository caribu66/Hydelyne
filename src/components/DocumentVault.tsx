import React, { useState, useMemo } from 'react';
import { UserProfile, SpecialistDocument, DocumentCategory } from '../types';
import { getDocumentComplianceStatus } from '../hooks/useSpecialistDocuments';
import { DocumentPreviewModal } from './DocumentPreviewModal';
import { DocumentUploadModal } from './DocumentUploadModal';
import {
  FileText,
  ShieldCheck,
  UploadCloud,
  Download,
  Eye,
  Trash2,
  Calendar,
  AlertTriangle,
  CheckCircle2,
  FileCheck,
  FileBadge,
  Activity,
  FolderArchive,
  ExternalLink,
  ArrowUpDown,
  Clock,
  Search,
  Sparkles,
  Check,
} from 'lucide-react';

export type DocumentSortOption = 'uploaded-desc' | 'uploaded-asc' | 'expiry-asc' | 'title-asc';

interface DocumentVaultProps {
  profile: UserProfile;
  documents: SpecialistDocument[];
  onAddDocument: (doc: Omit<SpecialistDocument, 'id' | 'uploadedAt'>) => void;
  onRemoveDocument: (docId: string) => void;
  onShowToast: (msg: string) => void;
  compact?: boolean;
}

export const DocumentVault: React.FC<DocumentVaultProps> = ({
  profile,
  documents,
  onAddDocument,
  onRemoveDocument,
  onShowToast,
  compact = false,
}) => {
  const [selectedDoc, setSelectedDoc] = useState<SpecialistDocument | null>(null);
  const [isUploadOpen, setIsUploadOpen] = useState(false);
  const [activeCategory, setActiveCategory] = useState<string>('all');
  const [sortOption, setSortOption] = useState<DocumentSortOption>('uploaded-desc');
  const [searchQuery, setSearchQuery] = useState('');

  // Compute metrics
  const totalCount = documents.length;
  const expiredCount = documents.filter((d) => getDocumentComplianceStatus(d).status === 'expired').length;
  const expiringSoonCount = documents.filter((d) => getDocumentComplianceStatus(d).status === 'expiring_soon').length;
  const validCount = documents.filter(
    (d) => getDocumentComplianceStatus(d).status === 'valid' || getDocumentComplianceStatus(d).status === 'no_expiry'
  ).length;

  // Auto-sort documents by upload date (newest first) by default
  const sortedAndFilteredDocs = useMemo(() => {
    return [...documents]
      .filter((doc) => {
        if (activeCategory !== 'all' && doc.category !== activeCategory) {
          return false;
        }
        if (searchQuery.trim()) {
          const q = searchQuery.toLowerCase();
          return (
            doc.title.toLowerCase().includes(q) ||
            doc.fileName.toLowerCase().includes(q) ||
            (doc.notes && doc.notes.toLowerCase().includes(q))
          );
        }
        return true;
      })
      .sort((a, b) => {
        if (sortOption === 'uploaded-desc') {
          const timeA = a.uploadedAt ? new Date(a.uploadedAt).getTime() : (a.issueDate ? new Date(a.issueDate).getTime() : 0);
          const timeB = b.uploadedAt ? new Date(b.uploadedAt).getTime() : (b.issueDate ? new Date(b.issueDate).getTime() : 0);
          return timeB - timeA;
        }
        if (sortOption === 'uploaded-asc') {
          const timeA = a.uploadedAt ? new Date(a.uploadedAt).getTime() : (a.issueDate ? new Date(a.issueDate).getTime() : 0);
          const timeB = b.uploadedAt ? new Date(b.uploadedAt).getTime() : (b.issueDate ? new Date(b.issueDate).getTime() : 0);
          return timeA - timeB;
        }
        if (sortOption === 'expiry-asc') {
          if (!a.expiryDate && !b.expiryDate) return 0;
          if (!a.expiryDate) return 1;
          if (!b.expiryDate) return -1;
          return new Date(a.expiryDate).getTime() - new Date(b.expiryDate).getTime();
        }
        if (sortOption === 'title-asc') {
          return a.title.localeCompare(b.title);
        }
        return 0;
      });
  }, [documents, activeCategory, searchQuery, sortOption]);

  const formatUploadDate = (isoString?: string): string => {
    if (!isoString) return 'Archived';
    try {
      const date = new Date(isoString);
      if (isNaN(date.getTime())) return 'Archived';
      return date.toLocaleDateString('en-GB', {
        day: 'numeric',
        month: 'short',
        year: 'numeric',
      });
    } catch {
      return 'Archived';
    }
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

  const handleDownloadSingle = (doc: SpecialistDocument, e: React.MouseEvent) => {
    e.stopPropagation();
    if (doc.fileUrl && doc.fileUrl.startsWith('data:')) {
      const a = window.document.createElement('a');
      a.href = doc.fileUrl;
      a.download = doc.fileName || `${doc.title}.pdf`;
      window.document.body.appendChild(a);
      a.click();
      window.document.body.removeChild(a);
      onShowToast(`Downloaded ${doc.fileName}`);
      return;
    }

    const content = `HYDENLYNE TALENT NETWORK - COMPLIANCE ARCHIVE\nDOCUMENT: ${doc.title}\nSPECIALIST: ${profile.name}\nCATEGORY: ${doc.category.toUpperCase()}\nEXPIRY: ${doc.expiryDate || 'Permanent'}\nUPLOADED: ${new Date(doc.uploadedAt).toLocaleString()}\nSTATUS: VERIFIED`;
    const blob = new Blob([content], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = window.document.createElement('a');
    a.href = url;
    a.download = `${doc.fileName}.txt`;
    window.document.body.appendChild(a);
    a.click();
    window.document.body.removeChild(a);
    URL.revokeObjectURL(url);
    onShowToast(`Downloaded ${doc.fileName}`);
  };

  const handleDownloadAllBundle = () => {
    const summary = documents
      .map((d, i) => {
        const compliance = getDocumentComplianceStatus(d);
        return `[${i + 1}] ${d.title}\nCategory: ${d.category.toUpperCase()} | File: ${d.fileName}\nUploaded: ${new Date(d.uploadedAt).toLocaleString()} | Validity: ${compliance.label} | Issued: ${d.issueDate || 'N/A'}\nNotes: ${d.notes || 'None'}\n`;
      })
      .join('\n----------------------------------------\n');

    const manifest = `HYDENLYNE COMPLIANCE BUNDLE MANIFEST
===================================================
SPECIALIST: ${profile.name}
DISCIPLINE: ${profile.department} (${profile.title})
TOTAL CREDENTIALS: ${documents.length}
MOBILISATION COMPLIANCE: ${expiredCount === 0 ? '100% AUDIT COMPLIANT (CLEARED)' : 'ACTION REQUIRED'}
GENERATED AT: ${new Date().toLocaleString()}
===================================================

DOCUMENT REGISTRATION INVENTORY:
----------------------------------------
${summary}
===================================================
All documents have been digitally archived for offshore mobilization verification.`;

    const blob = new Blob([manifest], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = window.document.createElement('a');
    a.href = url;
    a.download = `${profile.name.replace(/\s+/g, '_')}_Compliance_Bundle.txt`;
    window.document.body.appendChild(a);
    a.click();
    window.document.body.removeChild(a);
    URL.revokeObjectURL(url);
    onShowToast(`Exported complete compliance bundle for ${profile.name.split(' ')[0]}`);
  };

  return (
    <div className="space-y-3">
      {/* Compliance Header & Action Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2.5 bg-zinc-950/80 border border-zinc-800 rounded-xl p-3">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-zinc-900 border border-zinc-750 flex items-center justify-center text-zinc-300 shrink-0">
            <ShieldCheck className="w-4 h-4 text-zinc-300" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-xs font-bold text-zinc-100">Compliance & Document Vault</span>
              <span className="px-1.5 py-0.2 rounded bg-zinc-800 text-zinc-300 font-mono text-[10px]">
                {totalCount} files
              </span>
            </div>
            <p className="text-[11px] text-zinc-400">
              {expiredCount > 0 ? (
                <span className="text-rose-400 font-medium">⚠️ {expiredCount} document expired</span>
              ) : expiringSoonCount > 0 ? (
                <span className="text-amber-400 font-medium">⚠️ {expiringSoonCount} document expiring soon</span>
              ) : (
                <span className="text-emerald-400 font-medium">✓ 100% offshore mobilization compliant</span>
              )}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2 self-end sm:self-center">
          {totalCount > 0 && (
            <button
              type="button"
              onClick={handleDownloadAllBundle}
              className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-300 hover:text-white text-xs font-medium transition-colors cursor-pointer"
              title="Download full compliance manifest"
            >
              <FolderArchive className="w-3.5 h-3.5" />
              <span className="hidden md:inline">Export Bundle</span>
            </button>
          )}

          <button
            type="button"
            onClick={() => setIsUploadOpen(true)}
            className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold transition-colors cursor-pointer shadow-xs"
          >
            <UploadCloud className="w-3.5 h-3.5" />
            <span>Upload Document</span>
          </button>
        </div>
      </div>

      {/* Auto-Sort and Filter Toolbar */}
      {!compact && (
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2.5 bg-zinc-900/50 border border-zinc-800/80 rounded-xl p-2.5">
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
                className={`px-2.5 py-1 rounded-lg text-xs font-medium border transition-colors shrink-0 cursor-pointer ${
                  activeCategory === cat.id
                    ? 'bg-zinc-800 text-white border-zinc-600 font-semibold shadow-2xs'
                    : 'bg-zinc-950/60 text-zinc-400 border-zinc-850 hover:text-zinc-200'
                }`}
              >
                {cat.label} {cat.count > 0 && <span className="opacity-70 font-mono text-[10px]">({cat.count})</span>}
              </button>
            ))}
          </div>

          {/* Auto-Sort Control Strip */}
          <div className="flex items-center gap-2 shrink-0 self-end sm:self-center">
            <div className="flex items-center gap-1.5 text-xs">
              <span className="text-zinc-400 flex items-center gap-1 font-mono text-[11px]">
                <ArrowUpDown className="w-3 h-3 text-zinc-400" />
                <span className="hidden md:inline">Sort:</span>
              </span>
              <select
                id="document-sort-select"
                value={sortOption}
                onChange={(e) => setSortOption(e.target.value as DocumentSortOption)}
                className="bg-zinc-950 border border-zinc-750 text-zinc-200 text-xs rounded-lg px-2.5 py-1 font-medium focus:outline-hidden focus:ring-1 focus:ring-blue-500 cursor-pointer"
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
                className="px-2 py-0.5 rounded-md bg-blue-500/10 border border-blue-500/20 text-blue-400 text-[10px] font-mono font-medium flex items-center gap-1"
                title="Auto-sort is actively organizing files newest upload first"
              >
                <Sparkles className="w-2.5 h-2.5" />
                <span>Auto-Sorted</span>
              </span>
            )}
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
                className="group p-3 rounded-xl bg-zinc-900/60 hover:bg-zinc-900 border border-zinc-800 hover:border-zinc-750 transition-all cursor-pointer flex items-center justify-between gap-3 shadow-xs"
              >
                <div className="flex items-center gap-3 min-w-0 flex-1">
                  <div className="w-9 h-9 rounded-lg bg-zinc-800/80 border border-zinc-700/60 flex items-center justify-center text-zinc-300 shrink-0 group-hover:border-zinc-600 transition-colors">
                    <IconComponent className="w-4 h-4" />
                  </div>

                  <div className="min-w-0 flex-1 space-y-0.5">
                    <div className="flex items-center gap-2">
                      <h4 className="text-xs font-semibold text-zinc-200 group-hover:text-white transition-colors truncate">
                        {doc.title}
                      </h4>
                      {doc.isVerified && (
                        <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0" title="Verified Credential" />
                      )}
                      {isLatest && (
                        <span className="px-1.5 py-0.2 rounded bg-zinc-800 border border-zinc-700 text-zinc-300 font-mono text-[9px] font-medium shrink-0">
                          Latest Upload
                        </span>
                      )}
                    </div>

                    <div className="flex items-center gap-2 text-[11px] text-zinc-400 flex-wrap">
                      <span className="font-mono text-zinc-400">{doc.fileName}</span>
                      {doc.fileSize && <span>• {doc.fileSize}</span>}
                      <span>•</span>
                      <span className="flex items-center gap-1 font-mono text-zinc-400" title={`Uploaded: ${new Date(doc.uploadedAt).toLocaleString()}`}>
                        <Clock className="w-3 h-3 text-zinc-400" />
                        <span>Uploaded {formatUploadDate(doc.uploadedAt)}</span>
                      </span>
                      <span>•</span>
                      <span className={`px-2 py-0.2 rounded text-[10px] font-semibold border ${compliance.badgeClass}`}>
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
                    className="p-1.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-400 hover:text-white transition-colors cursor-pointer"
                    title="Download File"
                  >
                    <Download className="w-3.5 h-3.5" />
                  </button>

                  <button
                    type="button"
                    onClick={() => setSelectedDoc(doc)}
                    className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-300 hover:text-white font-medium text-xs transition-colors cursor-pointer border border-zinc-700/60"
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
        <div className="text-center py-6 border border-dashed border-zinc-800 rounded-xl bg-zinc-950/40 space-y-2">
          <FileText className="w-6 h-6 text-zinc-600 mx-auto" />
          <p className="text-xs text-zinc-400">No documents found in this category.</p>
          <button
            type="button"
            onClick={() => setIsUploadOpen(true)}
            className="text-xs text-blue-400 hover:underline font-medium"
          >
            Upload first document
          </button>
        </div>
      )}

      {/* Upload Modal */}
      <DocumentUploadModal
        isOpen={isUploadOpen}
        onClose={() => setIsUploadOpen(false)}
        profile={profile}
        onAddDocument={onAddDocument}
        onShowToast={onShowToast}
      />

      {/* Preview Modal */}
      <DocumentPreviewModal
        isOpen={Boolean(selectedDoc)}
        onClose={() => setSelectedDoc(null)}
        document={selectedDoc}
        profile={profile}
        onDelete={(docId) => onRemoveDocument(docId)}
        onShowToast={onShowToast}
      />
    </div>
  );
};
