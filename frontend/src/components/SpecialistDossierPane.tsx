import { FC, useEffect, useRef, useState, lazy, Suspense } from 'react';
import { useMutation } from '@apollo/client';
import { UserProfile, SpecialistDocument } from '../types';
import { CREW_MEMBERS_QUERY, VERIFY_CERTIFICATION } from '../lib/queries';
import { DocumentVault } from './DocumentVault';
import { ConfirmDialog } from './ConfirmDialog';
import {
  DossierHeader,
  DossierTabType,
  DossierBottomBar,
  DossierOverviewTab,
  DossierExperienceTab,
  DossierCredentialsTab,
  DossierExpertiseTab,
  DossierSystemsTab,
  DossierRadarTab,
} from './dossier';
import { Compass } from 'lucide-react';

const DocumentPreviewModal = lazy(() =>
  import('./DocumentPreviewModal').then((module) => ({ default: module.DocumentPreviewModal })),
);
const DossierRadarModal = lazy(() =>
  import('./dossier/DossierRadarModal').then((module) => ({ default: module.DossierRadarModal })),
);

interface SpecialistDossierPaneProps {
  profile: UserProfile | null;
  searchQuery?: string;
  isBookmarked: boolean;
  onToggleBookmark: (id: string) => void;
  onShowToast: (msg: string) => void;
  isCompared?: boolean;
  onToggleCompare?: (profile: UserProfile) => void;
  onRequestMobilization?: (profile: UserProfile) => void;
  onPrintDossier?: (profile: UserProfile) => void;
  documents?: SpecialistDocument[];
  summary?: string;
  summaryLoading?: boolean;
  onAddDocument?: () => void;
  onRemoveDocument?: (docId: string) => void | Promise<void>;
  onReviewDocument?: (docId: string, action: 'approve' | 'reject') => void | Promise<void>;
  canManageDocuments?: boolean;
  canRequestDocuments?: boolean;
  canDeleteCrew?: boolean;
  onDeleteCrew?: (profile: UserProfile) => Promise<void>;
  isFocusMode?: boolean;
  onToggleFocusMode?: () => void;
  onPrevProfile?: () => void;
  onNextProfile?: () => void;
  profileIndex?: number;
  totalProfiles?: number;
}

export const SpecialistDossierPane: FC<SpecialistDossierPaneProps> = ({
  profile,
  searchQuery = '',
  isBookmarked,
  onToggleBookmark,
  onShowToast,
  isCompared = false,
  onToggleCompare,
  onRequestMobilization,
  onPrintDossier,
  documents = [],
  summary,
  summaryLoading = false,
  onAddDocument,
  onRemoveDocument,
  onReviewDocument,
  canManageDocuments = false,
  canRequestDocuments = false,
  canDeleteCrew = false,
  onDeleteCrew,
  isFocusMode = false,
  onToggleFocusMode,
  onPrevProfile,
  onNextProfile,
  profileIndex,
  totalProfiles,
}) => {
  const [activeTab, setActiveTab] = useState<DossierTabType>('dossier');
  const [isRadarModalOpen, setIsRadarModalOpen] = useState(false);
  const [isDeleteConfirmOpen, setIsDeleteConfirmOpen] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [skillsQuery, setSkillsQuery] = useState('');
  const contentRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    contentRef.current?.scrollTo({ top: 0, behavior: 'auto' });
  }, [profile?.id, activeTab, isFocusMode]);

  const [previewDoc, setPreviewDoc] = useState<SpecialistDocument | null>(null);
  const [actionCertId, setActionCertId] = useState<string | null>(null);
  const [localVerificationOverrides, setLocalVerificationOverrides] = useState<
    Record<string, { verificationStatus: string; status?: string }>
  >({});

  const [verifyMutation, { loading: isVerifying }] = useMutation(VERIFY_CERTIFICATION, {
    refetchQueries: [{ query: CREW_MEMBERS_QUERY, variables: { limit: 100, offset: 0 } }],
  });

  const handleVerify = async (certId: string, status: 'VERIFIED' | 'REJECTED') => {
    setActionCertId(certId);
    const newVerificationStatus = status === 'VERIFIED' ? 'verified' : 'rejected';
    const newLifecycleStatus = status === 'VERIFIED' ? 'valid' : 'pending_verification';

    setLocalVerificationOverrides((prev) => ({
      ...prev,
      [certId]: { verificationStatus: newVerificationStatus, status: newLifecycleStatus },
    }));

    try {
      const res = await verifyMutation({
        variables: { id: certId, status },
      });
      if (res.errors && res.errors.length > 0) {
        const firstError = res.errors[0];
        throw new Error(firstError?.message ?? 'Verification mutation returned errors');
      }
      onShowToast(status === 'VERIFIED' ? 'Certification verified' : 'Certification rejected');
    } catch (err: unknown) {
      setLocalVerificationOverrides((prev) => {
        const next = { ...prev };
        delete next[certId];
        return next;
      });
      const message = err instanceof Error ? err.message : 'Action failed';
      onShowToast(`Failed: ${message}`);
    } finally {
      setActionCertId(null);
    }
  };

  useEffect(() => {
    setSkillsQuery('');
    setLocalVerificationOverrides({});
    setPreviewDoc(null);
  }, [profile?.id]);

  if (!profile) {
    return (
      <div className="h-full min-h-[460px] flex flex-col items-center justify-center p-8 text-center bg-surface/30 border border-border-subtle/60 rounded-[14px]">
        <div className="w-14 h-14 rounded-[14px] bg-surface border border-border-subtle flex items-center justify-center text-muted mb-3 shadow-inner">
          <Compass className="w-7 h-7 text-muted" />
        </div>
        <h3 className="text-sm font-semibold text-secondary">No Contractor Selected</h3>
        <p className="text-xs text-muted max-w-xs mt-1">
          Select a contractor from the list or press{' '}
          <kbd className="px-1.5 py-0.5 rounded bg-surface-raised border border-border-strong text-xs text-secondary font-mono">
            ↑
          </kbd>{' '}
          <kbd className="px-1.5 py-0.5 rounded bg-surface-raised border border-border-strong text-xs text-secondary font-mono">
            ↓
          </kbd>{' '}
          to review their dossier, skills radar, and compliance documents.
        </p>
      </div>
    );
  }

  const handleDeleteCrew = async () => {
    if (!onDeleteCrew) return;
    setIsDeleting(true);
    try {
      await onDeleteCrew(profile);
      setIsDeleteConfirmOpen(false);
    } catch (error) {
      onShowToast(error instanceof Error ? error.message : `Could not delete ${profile.name}`);
    } finally {
      setIsDeleting(false);
    }
  };

  const profileSkills = Array.from(new Set([...(profile.skills ?? []), ...(profile.expertise ?? [])]));

  return (
    <>
      <div
        id="specialist-focused-card"
        className={`bg-surface border border-border-subtle rounded-[14px] text-primary flex flex-col overflow-hidden shadow-2xl transition-all duration-300 ${
          isFocusMode
            ? 'w-full h-full max-w-6xl mx-auto ring-1 ring-focus shadow-black/80 my-2'
            : 'h-full'
        }`}
      >
        <DossierHeader
          profile={profile}
          isFocusMode={isFocusMode}
          onToggleFocusMode={onToggleFocusMode}
          onPrevProfile={onPrevProfile}
          onNextProfile={onNextProfile}
          profileIndex={profileIndex}
          totalProfiles={totalProfiles}
          searchQuery={searchQuery}
          isBookmarked={isBookmarked}
          onToggleBookmark={onToggleBookmark}
          isCompared={isCompared}
          onToggleCompare={onToggleCompare}
          onPrintDossier={onPrintDossier}
          canDeleteCrew={canDeleteCrew}
          onRequestDelete={() => setIsDeleteConfirmOpen(true)}
          activeTab={activeTab}
          onSelectTab={setActiveTab}
          profileSkillsCount={profileSkills.length}
          documentsCount={documents.length}
          onOpenRadarModal={() => setIsRadarModalOpen(true)}
        />

        {/* Scrollable Dossier Content */}
        <div
          ref={contentRef}
          className={`${
            isFocusMode
              ? 'focus-dossier-content overflow-y-auto p-2 sm:p-3 flex-1 text-xs'
              : 'overflow-y-auto p-5 flex-1 text-xs'
          } text-primary min-h-0`}
        >
          {activeTab === 'vault' ? (
            <DocumentVault
              profile={profile}
              documents={documents}
              onAddDocument={() => onAddDocument?.()}
              onRemoveDocument={(docId) => onRemoveDocument?.(docId)}
              onReviewDocument={onReviewDocument}
              canManageDocuments={canManageDocuments}
              canRequestDocuments={canRequestDocuments}
              onShowToast={onShowToast}
            />
          ) : activeTab === 'radar' ? (
            <DossierRadarTab profile={profile} isFocusMode={isFocusMode} />
          ) : activeTab === 'experience' ? (
            <DossierExperienceTab profile={profile} searchQuery={searchQuery} />
          ) : activeTab === 'systems' ? (
            <DossierSystemsTab profile={profile} />
          ) : activeTab === 'expertise' ? (
            <DossierExpertiseTab
              profile={profile}
              skillsQuery={skillsQuery}
              onSkillsQueryChange={setSkillsQuery}
            />
          ) : activeTab === 'credentials' ? (
            <DossierCredentialsTab
              profile={profile}
              documents={documents}
              canManageDocuments={canManageDocuments}
              localVerificationOverrides={localVerificationOverrides}
              isVerifying={isVerifying}
              actionCertId={actionCertId}
              onVerifyCertification={handleVerify}
              onPreviewDocument={setPreviewDoc}
            />
          ) : (
            <DossierOverviewTab
              profile={profile}
              isFocusMode={isFocusMode}
              searchQuery={searchQuery}
              summary={summary}
              summaryLoading={summaryLoading}
              documents={documents}
              onSelectTab={(tab) => setActiveTab(tab)}
            />
          )}
        </div>

        <DossierBottomBar
          profile={profile}
          isFocusMode={isFocusMode}
          onShowToast={onShowToast}
          onRequestMobilization={onRequestMobilization}
        />
      </div>

      <Suspense fallback={null}>
        <DossierRadarModal
          isOpen={isRadarModalOpen}
          onClose={() => setIsRadarModalOpen(false)}
          profile={profile}
        />
      </Suspense>

      <ConfirmDialog
        open={isDeleteConfirmOpen}
        title={`Delete ${profile.name}?`}
        description="This permanently removes the contractor, their certifications, work history, and managed documents. This cannot be undone."
        confirmLabel={isDeleting ? 'Deleting…' : 'Delete permanently'}
        onConfirm={() => void handleDeleteCrew()}
        onCancel={() => !isDeleting && setIsDeleteConfirmOpen(false)}
      />

      <Suspense fallback={null}>
        <DocumentPreviewModal
          isOpen={Boolean(previewDoc)}
          onClose={() => setPreviewDoc(null)}
          document={previewDoc}
          profile={profile}
          onShowToast={onShowToast}
          onDelete={canManageDocuments ? onRemoveDocument : undefined}
          onReviewAction={canManageDocuments ? onReviewDocument : undefined}
          canReview={canManageDocuments}
        />
      </Suspense>
    </>
  );
};
