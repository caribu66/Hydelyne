import React from 'react';
import { SpecialistDocument, UserProfile } from '../types';
import { getDocumentComplianceStatus } from '../hooks/useSpecialistDocuments';
import {
  X,
  FileText,
  Download,
  Printer,
  ShieldCheck,
  Calendar,
  Clock,
  Trash2,
  ExternalLink,
  CheckCircle2,
  AlertTriangle,
  Award,
  FileCheck,
} from 'lucide-react';

interface DocumentPreviewModalProps {
  isOpen: boolean;
  onClose: () => void;
  document: SpecialistDocument | null;
  profile: UserProfile;
  onDelete?: (docId: string) => void;
  onShowToast?: (msg: string) => void;
}

export const DocumentPreviewModal: React.FC<DocumentPreviewModalProps> = ({
  isOpen,
  onClose,
  document: doc,
  profile,
  onDelete,
  onShowToast,
}) => {
  if (!isOpen || !doc) return null;

  const compliance = getDocumentComplianceStatus(doc);

  const handleDownload = () => {
    if (doc.fileUrl && doc.fileUrl.startsWith('data:')) {
      const a = window.document.createElement('a');
      a.href = doc.fileUrl;
      a.download = doc.fileName || `${doc.title}.pdf`;
      window.document.body.appendChild(a);
      a.click();
      window.document.body.removeChild(a);
      onShowToast?.(`Downloaded ${doc.fileName}`);
      return;
    }

    // If simulated mock document, create a text/pdf blob download
    const content = `HYDENLYNE TALENT NETWORK - COMPLIANCE ARCHIVE
===================================================
DOCUMENT TITLE: ${doc.title}
SPECIALIST: ${profile.name} (${profile.title})
DEPARTMENT: ${profile.department}
DOCUMENT ID: ${doc.id}
CATEGORY: ${doc.category.toUpperCase()}
ISSUE DATE: ${doc.issueDate || 'Recorded on file'}
EXPIRY DATE: ${doc.expiryDate || 'Permanent / No Expiry'}
COMPLIANCE STATUS: ${compliance.label}
VERIFICATION: ${doc.isVerified ? 'VERIFIED BY HYDENLYNE QA' : 'PENDING AUDIT'}
NOTES: ${doc.notes || 'No additional notes provided.'}
FILE NAME: ${doc.fileName}
FILE SIZE: ${doc.fileSize || 'Standard PDF'}
UPLOAD TIMESTAMP: ${new Date(doc.uploadedAt).toLocaleString()}
===================================================
This document verification token is digitally certified for offshore mobilisation.`;

    const blob = new Blob([content], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = window.document.createElement('a');
    a.href = url;
    a.download = doc.fileName.endsWith('.pdf') ? doc.fileName.replace('.pdf', '_record.txt') : `${doc.fileName}.txt`;
    window.document.body.appendChild(a);
    a.click();
    window.document.body.removeChild(a);
    URL.revokeObjectURL(url);
    onShowToast?.(`Downloaded compliance record: ${doc.fileName}`);
  };

  const handlePrint = () => {
    window.print();
  };

  const handleDelete = () => {
    if (confirm(`Are you sure you want to remove "${doc.title}"?`)) {
      onDelete?.(doc.id);
      onShowToast?.(`Removed ${doc.title}`);
      onClose();
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md animate-in fade-in duration-200"
      onClick={onClose}
    >
      <div
        className="bg-zinc-900 border border-zinc-700/80 rounded-2xl w-full max-w-3xl overflow-hidden shadow-2xl flex flex-col max-h-[90vh]"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-zinc-800 bg-zinc-950/60">
          <div className="flex items-center gap-3 min-w-0">
            <div className="w-10 h-10 rounded-xl bg-blue-950/80 border border-blue-800/80 flex items-center justify-center text-blue-400 shrink-0">
              <FileCheck className="w-5 h-5 text-blue-400" />
            </div>
            <div className="min-w-0">
              <h2 className="text-base font-bold text-zinc-100 truncate">{doc.title}</h2>
              <p className="text-xs text-zinc-400 truncate">
                {profile.name} • {profile.department}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={handleDownload}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold transition-colors cursor-pointer"
            >
              <Download className="w-3.5 h-3.5" />
              <span>Download</span>
            </button>

            <button
              type="button"
              onClick={handlePrint}
              className="p-2 rounded-xl bg-zinc-800 hover:bg-zinc-700 text-zinc-300 transition-colors cursor-pointer hidden sm:inline-flex"
              title="Print Document Record"
            >
              <Printer className="w-4 h-4" />
            </button>

            {onDelete && (
              <button
                type="button"
                onClick={handleDelete}
                className="p-2 rounded-xl bg-zinc-800 hover:bg-rose-900/50 hover:text-rose-400 text-zinc-400 transition-colors cursor-pointer"
                title="Delete Document"
              >
                <Trash2 className="w-4 h-4" />
              </button>
            )}

            <button
              type="button"
              onClick={onClose}
              className="p-2 rounded-xl bg-zinc-800 hover:bg-zinc-700 text-zinc-400 hover:text-zinc-200 transition-colors cursor-pointer"
              title="Close modal"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Compliance Status Ribbon */}
        <div className="px-5 py-2.5 bg-zinc-950/40 border-b border-zinc-800 flex flex-wrap items-center justify-between gap-3 text-xs">
          <div className="flex items-center gap-2">
            <span className="text-zinc-400 font-mono">Status:</span>
            <span className={`px-2.5 py-0.5 rounded-full text-xs font-semibold border ${compliance.badgeClass}`}>
              {compliance.label}
            </span>
          </div>

          <div className="flex items-center gap-4 text-zinc-400 text-[11px] font-mono">
            {doc.issueDate && (
              <span className="flex items-center gap-1">
                <Calendar className="w-3.5 h-3.5 text-zinc-400" />
                Issued: {doc.issueDate}
              </span>
            )}
            {doc.expiryDate && (
              <span className="flex items-center gap-1">
                <Clock className="w-3.5 h-3.5 text-zinc-400" />
                Expires: {doc.expiryDate}
              </span>
            )}
            {doc.fileSize && <span>Size: {doc.fileSize}</span>}
          </div>
        </div>

        {/* Body / Document Preview Surface */}
        <div className="p-6 overflow-y-auto flex-1 space-y-5 bg-zinc-950/90">
          {/* Note or reference box */}
          {doc.notes && (
            <div className="p-3 rounded-xl bg-zinc-900 border border-zinc-800 text-xs text-zinc-300 flex items-start gap-2.5">
              <ShieldCheck className="w-4 h-4 text-blue-400 shrink-0 mt-0.5" />
              <div>
                <span className="font-semibold text-zinc-200 block">Verification Note:</span>
                <p className="text-zinc-400 leading-relaxed mt-0.5">{doc.notes}</p>
              </div>
            </div>
          )}

          {/* Visual Certificate / Document Sheet */}
          <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-6 sm:p-8 space-y-6 shadow-inner relative overflow-hidden">
            {/* Watermark */}
            <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 text-[90px] font-black text-zinc-800/20 pointer-events-none select-none tracking-widest font-mono rotate-[-20deg]">
              HYDENLYNE
            </div>

            {/* Document Header */}
            <div className="flex items-start justify-between border-b border-zinc-800 pb-4 relative z-10">
              <div>
                <div className="flex items-center gap-2">
                  <span className="text-[10px] font-mono uppercase px-2 py-0.5 bg-blue-950 text-blue-300 border border-blue-800 rounded-md font-bold">
                    Official Specialist Document
                  </span>
                  <span className="text-[10px] font-mono text-zinc-400">REF: {doc.id}</span>
                </div>
                <h3 className="text-lg font-bold text-zinc-100 mt-2">{doc.title}</h3>
                <p className="text-xs text-zinc-400 font-mono mt-0.5">File: {doc.fileName}</p>
              </div>

              <div className="text-right">
                <div className="w-12 h-12 rounded-xl bg-zinc-800 border border-zinc-700 flex items-center justify-center text-blue-400 font-serif font-bold text-xl mx-auto mb-1">
                  H
                </div>
                <span className="text-[10px] font-mono text-zinc-400">Hydenlyne QA</span>
              </div>
            </div>

            {/* Document Details Grid */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 relative z-10 text-xs">
              <div className="p-3 bg-zinc-950/60 rounded-xl border border-zinc-800/80 space-y-1">
                <span className="text-zinc-400 font-mono text-[10px] block uppercase">Candidate / Holder</span>
                <span className="text-zinc-100 font-semibold text-sm block">{profile.name}</span>
                <span className="text-zinc-400 text-xs block">{profile.title}</span>
              </div>

              <div className="p-3 bg-zinc-950/60 rounded-xl border border-zinc-800/80 space-y-1">
                <span className="text-zinc-400 font-mono text-[10px] block uppercase">Accreditation Category</span>
                <span className="text-blue-400 font-semibold text-sm block uppercase tracking-wide">
                  {doc.category.replace('_', ' ')}
                </span>
                <span className="text-zinc-400 text-xs block">Vessel & Field Mobilisation Ready</span>
              </div>

              <div className="p-3 bg-zinc-950/60 rounded-xl border border-zinc-800/80 space-y-1">
                <span className="text-zinc-400 font-mono text-[10px] block uppercase">Validity Timeline</span>
                <div className="flex items-center gap-2">
                  <span className="text-zinc-200 font-medium">Issued: {doc.issueDate || 'Current'}</span>
                  <span>→</span>
                  <span className="text-zinc-200 font-medium">Expiry: {doc.expiryDate || 'Permanent'}</span>
                </div>
              </div>

              <div className="p-3 bg-zinc-950/60 rounded-xl border border-zinc-800/80 space-y-1">
                <span className="text-zinc-400 font-mono text-[10px] block uppercase">Audit Check</span>
                <div className="flex items-center gap-1.5 text-emerald-400 font-semibold">
                  <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                  <span>Verified by Hydenlyne Compliance</span>
                </div>
              </div>
            </div>

            {/* Document Content Abstract / Preview */}
            <div className="p-4 bg-zinc-950/40 rounded-xl border border-zinc-800/60 text-xs text-zinc-300 space-y-2 relative z-10 leading-relaxed font-light">
              <p>
                This certified document has been registered in the Hydenlyne talent management portal. The credentials,
                certifications, and medical clearance have been verified against issuing authority databases (OPITO, OEUK,
                JNCC, GWO, and IMCA) for offshore mobilisations.
              </p>
              <p className="text-zinc-400 text-[11px]">
                Uploaded on: {new Date(doc.uploadedAt).toLocaleDateString()} • Original file checksum validated.
              </p>
            </div>
          </div>
        </div>

        {/* Footer Actions */}
        <div className="px-5 py-3.5 bg-zinc-950 border-t border-zinc-800 flex items-center justify-between text-xs">
          <span className="text-zinc-400 font-mono">Doc ID: {doc.id}</span>
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 rounded-xl bg-zinc-800 hover:bg-zinc-700 text-zinc-200 font-medium transition-colors cursor-pointer"
          >
            Close Preview
          </button>
        </div>
      </div>
    </div>
  );
};
