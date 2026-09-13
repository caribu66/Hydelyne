import { FC, useEffect, useRef, useState } from 'react';
import { useMutation, useQuery } from '@apollo/client';
import { Loader2, ShieldCheck, X } from 'lucide-react';
import { AnimatePresence, motion } from 'motion/react';
import { useAccessibleDialog } from '../hooks/useAccessibleDialog';
import { SET_STAFF_ROLE, STAFF_USERS_QUERY } from '../lib/queries';
import { apolloResultHasErrors, isSessionDataReady, isSessionQueryEnabled, isSessionRequestCurrent } from '../utils/sessionScope';

interface Account {
  id: string;
  fullName: string;
  email?: string | null;
  role: string;
}

interface ManageStaffModalProps {
  isOpen: boolean;
  sessionKey?: string | null;
  onClose: () => void;
}

export const ManageStaffModal: FC<ManageStaffModalProps> = ({ isOpen, sessionKey = null, onClose }) => {
  const dialogRef = useRef<HTMLDivElement>(null);
  const previousSessionKeyRef = useRef<string | null>(null);
  const currentSessionKeyRef = useRef(sessionKey);
  currentSessionKeyRef.current = sessionKey;
  const [loadedSessionKey, setLoadedSessionKey] = useState<string | null>(null);
  const [changingId, setChangingId] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [hasMore, setHasMore] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [visibleAccounts, setVisibleAccounts] = useState<Account[]>([]);
  const requestVersionRef = useRef(0);
  const refreshPendingSessionKeyRef = useRef<string | null>(null);
  const hasCommittedAccountsRef = useRef(false);
  const { data, loading, error, refetch, fetchMore } = useQuery<{ staffAccounts: Account[] }>(STAFF_USERS_QUERY, {
    skip: !isSessionQueryEnabled(isOpen, sessionKey),
    fetchPolicy: 'network-only',
    variables: { limit: 100, offset: 0 },
  });
  const [setStaffRole] = useMutation(SET_STAFF_ROLE);
  useAccessibleDialog(isOpen, dialogRef, onClose);

  useEffect(() => {
    requestVersionRef.current += 1;
    hasCommittedAccountsRef.current = false;
    setVisibleAccounts([]);
    setLoadedSessionKey(null);
    setHasMore(true);
    setLoadingMore(false);
    setChangingId(null);
    setActionError(null);
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
          if (apolloResultHasErrors(result)) throw new Error('Staff account refresh failed')
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
          hasCommittedAccountsRef.current = true;
          setVisibleAccounts(result.data?.staffAccounts ?? []);
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
      && !hasCommittedAccountsRef.current
    ) {
      hasCommittedAccountsRef.current = true;
      setVisibleAccounts(data?.staffAccounts ?? []);
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

  useEffect(() => {
    if (isOpen) setHasMore(true);
  }, [isOpen]);

  const accounts = (sessionReady ? visibleAccounts : []).filter((account) => account.role !== 'admin');

  const loadMore = async () => {
    if (!sessionReady || !sessionKey || currentSessionKeyRef.current !== sessionKey) return;
    const requestVersion = requestVersionRef.current;
    setLoadingMore(true);
    setActionError(null);
    try {
      const loadedCount = visibleAccounts.length;
      const next = await fetchMore({
        variables: { limit: 100, offset: loadedCount },
        updateQuery: (previous, { fetchMoreResult }) => ({
          staffAccounts: [...previous.staffAccounts, ...fetchMoreResult.staffAccounts],
        }),
      });
      if (apolloResultHasErrors(next)) throw new Error('Staff account page request failed');
      if (requestVersion !== requestVersionRef.current || currentSessionKeyRef.current !== sessionKey) return;
      setVisibleAccounts(next.data.staffAccounts);
      setHasMore(next.data.staffAccounts.length === 100);
    } catch (failure) {
      if (requestVersion !== requestVersionRef.current || currentSessionKeyRef.current !== sessionKey) return;
      setActionError(failure instanceof Error ? failure.message : 'Could not load more accounts');
    } finally {
      if (requestVersion === requestVersionRef.current && currentSessionKeyRef.current === sessionKey) {
        setLoadingMore(false);
      }
    }
  };

  const updateRole = async (account: Account) => {
    if (!sessionKey || currentSessionKeyRef.current !== sessionKey) return;
    const requestVersion = requestVersionRef.current;
    setChangingId(account.id);
    setActionError(null);
    try {
      const result = await setStaffRole({
        variables: { userId: account.id, enabled: account.role !== 'staff' },
      });
      if (apolloResultHasErrors(result)) throw new Error('Staff role update returned errors');
      if (requestVersion !== requestVersionRef.current || currentSessionKeyRef.current !== sessionKey) return;
      try {
        const refreshed = await refetch();
        if (apolloResultHasErrors(refreshed)) throw new Error('Staff account refresh failed');
        hasCommittedAccountsRef.current = true;
        setVisibleAccounts(refreshed.data?.staffAccounts ?? []);
      } catch {
        if (requestVersion === requestVersionRef.current && currentSessionKeyRef.current === sessionKey) {
          setActionError('Staff access was updated, but the account list could not be refreshed.');
        }
        return;
      }
      if (requestVersion !== requestVersionRef.current || currentSessionKeyRef.current !== sessionKey) return;
    } catch (failure) {
      if (requestVersion !== requestVersionRef.current || currentSessionKeyRef.current !== sessionKey) return;
      setActionError(failure instanceof Error ? failure.message : 'Could not update this account');
    } finally {
      if (requestVersion === requestVersionRef.current && currentSessionKeyRef.current === sessionKey) {
        setChangingId(null);
      }
    }
  };

  return (
    <AnimatePresence>
      {isOpen && <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-6">
      <motion.button type="button" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="fixed inset-0 bg-canvas/80 backdrop-blur-xs" onClick={onClose} aria-label="Close staff access" />
      <motion.div ref={dialogRef} initial={{ opacity: 0, scale: 0.97 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0.97 }} role="dialog" aria-modal="true" aria-labelledby="staff-access-title" className="relative z-10 flex max-h-[92vh] w-full max-w-2xl flex-col rounded-[14px] border border-border-subtle bg-surface p-5 shadow-2xl sm:p-6">
        <div className="flex items-center justify-between gap-3 border-b border-border-subtle pb-4">
          <div className="flex items-center gap-3">
            <span className="flex h-10 w-10 items-center justify-center rounded-lg bg-surface-raised"><ShieldCheck className="h-5 w-5 text-secondary" /></span>
            <div><h2 id="staff-access-title" className="text-sm font-semibold text-primary">Staff access</h2><p className="text-xs text-secondary">Choose who can add contractors and submit CVs.</p></div>
          </div>
          <button type="button" onClick={onClose} className="inline-flex min-h-11 min-w-11 items-center justify-center rounded-lg text-secondary hover:bg-surface-raised focus-visible:ring-2 focus-visible:ring-focus" aria-label="Close dialog"><X className="h-5 w-5" /></button>
        </div>
        <div className="mt-4 min-h-0 space-y-2 overflow-y-auto">
          {loading && <p className="flex items-center gap-2 text-sm text-secondary"><Loader2 className="h-4 w-4 animate-spin" />Loading accounts…</p>}
          {(error || actionError) && <p role="alert" className="rounded-lg border border-danger-border bg-danger-soft p-3 text-sm text-danger">{actionError || 'Could not load accounts.'}</p>}
          {!loading && accounts.length === 0 && <p className="text-sm text-secondary">No eligible accounts found.</p>}
          {accounts.map((account) => {
            const isStaff = account.role === 'staff';
            const isChanging = changingId === account.id;
            return <div key={account.id} className="flex items-center justify-between gap-4 rounded-lg border border-border-subtle bg-canvas/40 p-3"><div className="min-w-0"><p className="truncate text-sm font-semibold text-primary">{account.fullName}</p><p className="truncate text-xs text-secondary">{account.email || 'No email recorded'}</p></div><button type="button" onClick={() => void updateRole(account)} disabled={isChanging} className={`min-h-11 shrink-0 rounded-lg px-4 text-sm font-semibold focus-visible:ring-2 focus-visible:ring-focus ${isStaff ? 'border border-border-strong bg-surface text-secondary hover:bg-surface-raised' : 'bg-action text-on-action hover:bg-action-hover'}`}>{isChanging ? <Loader2 className="h-4 w-4 animate-spin" /> : isStaff ? 'Remove staff access' : 'Make staff'}</button></div>;
          })}
          {hasMore && visibleAccounts.length === 100 && <button type="button" onClick={() => void loadMore()} disabled={loadingMore} className="min-h-11 w-full rounded-lg border border-border-strong bg-surface px-4 text-sm font-semibold text-secondary hover:bg-surface-raised focus-visible:ring-2 focus-visible:ring-focus disabled:opacity-50">{loadingMore ? 'Loading…' : 'Load more accounts'}</button>}
        </div>
      </motion.div>
    </div>}
    </AnimatePresence>
  );
};
