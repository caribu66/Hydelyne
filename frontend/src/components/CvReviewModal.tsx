import { ChangeEvent, FC, useEffect, useRef, useState } from 'react';
import { useMutation, useQuery } from '@apollo/client';
import { AnimatePresence, motion } from 'motion/react';
import { Check, ClipboardCheck, Loader2, X } from 'lucide-react';
import { useAccessibleDialog } from '../hooks/useAccessibleDialog';
import { APPROVE_CV_REVIEW, CV_REVIEWS_QUERY, REJECT_CV_REVIEW } from '../lib/queries';
import { downloadDocumentFile } from '../lib/documentsApi';
import { apolloResultHasErrors, isSessionDataReady, isSessionQueryEnabled, isSessionRequestCurrent } from '../utils/sessionScope';
import { formatDocumentDate } from './documentVaultUtils';

interface CvReview {
  id: string;
  documentId: string;
  crewMemberId: string;
  status: string;
  proposedData?: string | null;
  reviewNote?: string | null;
  createdAt: string;
}

interface CvReviewModalProps {
  isOpen: boolean;
  isAdmin: boolean;
  sessionKey?: string | null;
  onClose: () => void;
  onApproved: () => void;
}

export const CvReviewModal: FC<CvReviewModalProps> = ({ isOpen, isAdmin, sessionKey = null, onClose, onApproved }) => {
  const dialogRef = useRef<HTMLDivElement>(null);
  const previousSessionKeyRef = useRef<string | null>(null);
  const currentSessionKeyRef = useRef(sessionKey);
  currentSessionKeyRef.current = sessionKey;
  const [loadedSessionKey, setLoadedSessionKey] = useState<string | null>(null);
  const { data, loading, error, refetch, fetchMore } = useQuery<{ cvReviews: CvReview[] }>(CV_REVIEWS_QUERY, {
    skip: !isSessionQueryEnabled(isOpen, sessionKey),
    fetchPolicy: 'network-only',
    variables: { limit: 100, offset: 0 },
  });
  const [approve, { loading: approving }] = useMutation(APPROVE_CV_REVIEW);
  const [reject, { loading: rejecting }] = useMutation(REJECT_CV_REVIEW);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [draftData, setDraftData] = useState('');
  const [note, setNote] = useState('');
  const [actionError, setActionError] = useState<string | null>(null);
  const [loadingMore, setLoadingMore] = useState(false);
  const [visibleReviews, setVisibleReviews] = useState<CvReview[]>([]);
  const [hasMore, setHasMore] = useState(true);
  const [downloadingDocument, setDownloadingDocument] = useState(false);
  const requestVersionRef = useRef(0);
  const refreshPendingSessionKeyRef = useRef<string | null>(null);
  const hasCommittedReviewsRef = useRef(false);
  useAccessibleDialog(isOpen, dialogRef, onClose);

  useEffect(() => {
    requestVersionRef.current += 1;
    hasCommittedReviewsRef.current = false;
    setVisibleReviews([]);
    setLoadedSessionKey(null);
    setSelectedId(null);
    setActionError(null);
    setDownloadingDocument(false);
    refreshPendingSessionKeyRef.current = null;
    if (!isOpen || !sessionKey) {
      previousSessionKeyRef.current = null;
      return;
    }

    const sessionChanged =
      previousSessionKeyRef.current !== null && previousSessionKeyRef.current !== sessionKey;
    previousSessionKeyRef.current = sessionKey;
    const requestVersion = requestVersionRef.current;
    let active = true;
    if (sessionChanged) {
      refreshPendingSessionKeyRef.current = sessionKey;
      void refetch()
        .then((result) => {
          if (apolloResultHasErrors(result)) throw new Error('CV review refresh failed')
          if (
            !active
            || !isSessionRequestCurrent(
              requestVersion,
              requestVersionRef.current,
              currentSessionKeyRef.current,
              sessionKey,
            )
            || refreshPendingSessionKeyRef.current !== sessionKey
          ) return;
          hasCommittedReviewsRef.current = true;
          setVisibleReviews(result.data?.cvReviews ?? []);
        })
        .catch(() => {})
        .finally(() => {
          if (active && refreshPendingSessionKeyRef.current === sessionKey) {
            refreshPendingSessionKeyRef.current = null;
          }
        });
    }
    return () => {
      active = false;
    };
  }, [isOpen, refetch, sessionKey]);

  useEffect(() => {
    if (
      isOpen
      && sessionKey
      && loadedSessionKey === sessionKey
      && !hasCommittedReviewsRef.current
    ) {
      hasCommittedReviewsRef.current = true;
      setVisibleReviews(data?.cvReviews ?? []);
    }
  }, [data, isOpen, loadedSessionKey, sessionKey]);

  useEffect(() => {
    if (
      isOpen
      && sessionKey
      && !loading
      && !error
      && refreshPendingSessionKeyRef.current !== sessionKey
    ) setLoadedSessionKey(sessionKey);
  }, [error, isOpen, loading, sessionKey]);

  const sessionReady = isSessionDataReady(isOpen, loadedSessionKey, sessionKey, loading, error);
  const reviews = sessionReady ? visibleReviews : [];
  const selected = reviews.find((review) => review.id === selectedId) ?? reviews[0];

  useEffect(() => {
    if (isOpen) setHasMore(true);
  }, [isOpen]);

  useEffect(() => {
    if (!selected) return;
    setSelectedId(selected.id);
    try {
      setDraftData(JSON.stringify(JSON.parse(selected.proposedData ?? '{}'), null, 2));
    } catch {
      setDraftData('{}');
    }
    setNote(selected.reviewNote ?? '');
    setActionError(null);
  }, [selected]);

  const handleApprove = async () => {
    if (!selected || !sessionKey || currentSessionKeyRef.current !== sessionKey) return;
    const requestVersion = requestVersionRef.current;
    try {
      JSON.parse(draftData);
      const result = await approve({
        variables: { reviewId: selected.id, approvedData: draftData, note: note || undefined },
      });
      if (apolloResultHasErrors(result)) throw new Error('CV approval returned errors');
      if (requestVersion !== requestVersionRef.current || currentSessionKeyRef.current !== sessionKey) return;
      try {
        const refreshed = await refetch();
        if (apolloResultHasErrors(refreshed)) throw new Error('CV review refresh failed');
        hasCommittedReviewsRef.current = true;
        setVisibleReviews(refreshed.data?.cvReviews ?? []);
      } catch {
        if (requestVersion === requestVersionRef.current && currentSessionKeyRef.current === sessionKey) {
          setActionError('CV was approved, but the review list could not be refreshed.');
        }
        return;
      }
      if (requestVersion !== requestVersionRef.current || currentSessionKeyRef.current !== sessionKey) return;
      onApproved();
    } catch (actionFailure) {
      if (requestVersion !== requestVersionRef.current || currentSessionKeyRef.current !== sessionKey) return;
      setActionError(actionFailure instanceof Error ? actionFailure.message : 'Could not approve this CV');
    }
  };

  const handleReject = async () => {
    if (!selected || !sessionKey || currentSessionKeyRef.current !== sessionKey) return;
    if (!note.trim()) {
      setActionError('Add a reason before rejecting this CV.');
      return;
    }
    const requestVersion = requestVersionRef.current;
    try {
      const result = await reject({ variables: { reviewId: selected.id, note: note.trim() } });
      if (apolloResultHasErrors(result)) throw new Error('CV rejection returned errors');
      if (requestVersion !== requestVersionRef.current || currentSessionKeyRef.current !== sessionKey) return;
      try {
        const refreshed = await refetch();
        if (apolloResultHasErrors(refreshed)) throw new Error('CV review refresh failed');
        hasCommittedReviewsRef.current = true;
        setVisibleReviews(refreshed.data?.cvReviews ?? []);
      } catch {
        if (requestVersion === requestVersionRef.current && currentSessionKeyRef.current === sessionKey) {
          setActionError('CV was rejected, but the review list could not be refreshed.');
        }
        return;
      }
      if (requestVersion !== requestVersionRef.current || currentSessionKeyRef.current !== sessionKey) return;
    } catch (actionFailure) {
      if (requestVersion !== requestVersionRef.current || currentSessionKeyRef.current !== sessionKey) return;
      setActionError(actionFailure instanceof Error ? actionFailure.message : 'Could not reject this CV');
    }
  };

  const handleDataChange = (event: ChangeEvent<HTMLTextAreaElement>) => setDraftData(event.target.value);

  const handleDownloadOriginal = async () => {
    if (!selected || !sessionKey || currentSessionKeyRef.current !== sessionKey) return;
    const requestVersion = requestVersionRef.current;
    setDownloadingDocument(true);
    try {
      await downloadDocumentFile(selected.documentId, `cv-${selected.documentId}.pdf`);
    } catch (actionFailure) {
      if (requestVersion !== requestVersionRef.current || currentSessionKeyRef.current !== sessionKey) return;
      setActionError(actionFailure instanceof Error ? actionFailure.message : 'Could not download this CV');
    } finally {
      if (requestVersion === requestVersionRef.current && currentSessionKeyRef.current === sessionKey) {
        setDownloadingDocument(false);
      }
    }
  };

  const loadMore = async () => {
    if (!sessionKey || currentSessionKeyRef.current !== sessionKey || !sessionReady) return;
    const requestVersion = requestVersionRef.current;
    setLoadingMore(true);
    setActionError(null);
    try {
      const next = await fetchMore({
        variables: { limit: 100, offset: reviews.length },
        updateQuery: (previous, { fetchMoreResult }) => ({
          cvReviews: [...previous.cvReviews, ...fetchMoreResult.cvReviews],
        }),
      });
      if (apolloResultHasErrors(next)) throw new Error('CV review page request failed');
      if (requestVersion !== requestVersionRef.current || currentSessionKeyRef.current !== sessionKey) return;
      setVisibleReviews(next.data.cvReviews);
      setHasMore(next.data.cvReviews.length === 100);
    } catch (failure) {
      if (requestVersion !== requestVersionRef.current || currentSessionKeyRef.current !== sessionKey) return;
      setActionError(failure instanceof Error ? failure.message : 'Could not load more submissions');
    } finally {
      if (requestVersion === requestVersionRef.current && currentSessionKeyRef.current === sessionKey) {
        setLoadingMore(false);
      }
    }
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-6">
          <motion.button type="button" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="fixed inset-0 bg-canvas/80 backdrop-blur-xs" onClick={onClose} aria-label="Close CV reviews" />
          <motion.div ref={dialogRef} initial={{ opacity: 0, scale: 0.97 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0.97 }} role="dialog" aria-modal="true" aria-labelledby="cv-review-title" className="relative z-10 flex max-h-[92vh] w-full max-w-4xl flex-col rounded-[14px] border border-border-subtle bg-surface p-5 shadow-2xl sm:p-6">
            <div className="flex items-center justify-between gap-3 border-b border-border-subtle pb-4">
              <div className="flex items-center gap-3"><span className="flex h-10 w-10 items-center justify-center rounded-lg bg-surface-raised"><ClipboardCheck className="h-5 w-5 text-secondary" /></span><div><h2 id="cv-review-title" className="text-sm font-semibold text-primary">CV submissions</h2><p className="text-xs text-secondary">{isAdmin ? 'Review and publish extracted CV information.' : 'Track CVs you submitted.'}</p></div></div>
              <button type="button" onClick={onClose} className="inline-flex min-h-11 min-w-11 items-center justify-center rounded-lg text-secondary hover:bg-surface-raised focus-visible:ring-2 focus-visible:ring-focus" aria-label="Close dialog"><X className="h-5 w-5" /></button>
            </div>
            <div className="mt-4 grid min-h-0 flex-1 gap-4 overflow-hidden md:grid-cols-[240px_1fr]">
              <div className="space-y-2 overflow-y-auto">
                {loading && <p className="flex items-center gap-2 text-sm text-muted"><Loader2 className="h-4 w-4 animate-spin" />Loading submissions…</p>}
                {error && <p className="text-sm text-danger">Could not load CV submissions.</p>}
                {actionError && <p role="alert" className="rounded-lg border border-danger-border bg-danger-soft p-3 text-sm text-danger">{actionError}</p>}
                {!loading && reviews.length === 0 && <p className="text-sm text-muted">No CV submissions yet.</p>}
                {reviews.map((review) => <button key={review.id} type="button" onClick={() => setSelectedId(review.id)} className={`w-full rounded-lg border p-3 text-left focus-visible:ring-2 focus-visible:ring-focus ${selected?.id === review.id ? 'border-border-strong bg-surface-raised' : 'border-border-subtle bg-canvas/40'}`}><span className="block text-sm font-semibold text-primary">Submission {review.id.slice(0, 8)}</span><span className="mt-1 block text-xs capitalize text-secondary">{review.status.replaceAll('_', ' ')}</span><span className="mt-1 block text-xs text-secondary">{formatDocumentDate(review.createdAt)}</span></button>)}
                {hasMore && reviews.length === 100 && <button type="button" onClick={() => void loadMore()} disabled={loadingMore} className="min-h-11 w-full rounded-lg border border-border-strong bg-surface px-3 text-sm font-semibold text-secondary hover:bg-surface-raised focus-visible:ring-2 focus-visible:ring-focus disabled:opacity-50">{loadingMore ? 'Loading…' : 'Load more'}</button>}
              </div>
              {selected && <div className="min-h-0 space-y-3 overflow-y-auto rounded-[14px] border border-border-subtle bg-canvas/40 p-4">
                <div><p className="text-xs font-mono uppercase tracking-wider text-muted">Status</p><p className="text-sm font-semibold capitalize text-primary">{selected.status.replaceAll('_', ' ')}</p></div>
                {isAdmin && selected.status === 'awaiting_review' ? <>
                  <button type="button" onClick={() => void handleDownloadOriginal()} disabled={downloadingDocument} className="inline-flex min-h-11 items-center rounded-lg border border-border-strong bg-surface px-4 text-sm font-semibold text-secondary hover:bg-surface-raised focus-visible:ring-2 focus-visible:ring-focus disabled:opacity-50">{downloadingDocument ? 'Downloading…' : 'Download original CV'}</button>
                  <label className="block text-sm font-semibold text-primary">Extracted CV information<textarea value={draftData} onChange={handleDataChange} className="mt-2 min-h-64 w-full rounded-lg border border-border-strong bg-surface p-3 font-mono text-xs text-primary focus-visible:ring-2 focus-visible:ring-focus" spellCheck={false} /></label>
                  <label className="block text-sm font-semibold text-primary">Review note<textarea value={note} onChange={(event) => setNote(event.target.value)} className="mt-2 min-h-20 w-full rounded-lg border border-border-strong bg-surface p-3 text-sm text-primary focus-visible:ring-2 focus-visible:ring-focus" /></label>
                  <div className="flex flex-wrap justify-end gap-2"><button type="button" onClick={handleReject} disabled={rejecting || approving} className="min-h-11 rounded-lg border border-danger-border px-4 text-sm font-semibold text-danger hover:bg-danger-soft focus-visible:ring-2 focus-visible:ring-focus">Reject</button><button type="button" onClick={handleApprove} disabled={rejecting || approving} className="inline-flex min-h-11 items-center gap-2 rounded-lg bg-action px-4 text-sm font-semibold text-on-action hover:bg-action-hover focus-visible:ring-2 focus-visible:ring-focus">{approving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Check className="h-4 w-4" />}Approve and publish</button></div>
                </> : <p className="text-sm text-secondary">{selected.status === 'approved' ? 'This profile is approved and searchable.' : selected.status === 'rejected' ? selected.reviewNote || 'This submission was rejected.' : 'The CV is still being processed.'}</p>}
              </div>}
            </div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
};
