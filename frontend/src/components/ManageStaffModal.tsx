import { FC, useEffect, useRef, useState } from 'react';
import { useMutation, useQuery } from '@apollo/client';
import { Loader2, ShieldCheck, X } from 'lucide-react';
import { AnimatePresence, motion } from 'motion/react';
import { useAccessibleDialog } from '../hooks/useAccessibleDialog';
import { SET_STAFF_ROLE, STAFF_USERS_QUERY } from '../lib/queries';

interface Account {
  id: string;
  fullName: string;
  email?: string | null;
  role: string;
}

interface ManageStaffModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const ManageStaffModal: FC<ManageStaffModalProps> = ({ isOpen, onClose }) => {
  const dialogRef = useRef<HTMLDivElement>(null);
  const [changingId, setChangingId] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [hasMore, setHasMore] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const { data, loading, error, refetch, fetchMore } = useQuery<{ crewMembers: Account[] }>(STAFF_USERS_QUERY, {
    skip: !isOpen,
    fetchPolicy: 'network-only',
    variables: { limit: 100, offset: 0 },
  });
  const [setStaffRole] = useMutation(SET_STAFF_ROLE);
  useAccessibleDialog(isOpen, dialogRef, onClose);

  useEffect(() => {
    if (isOpen) setHasMore(true);
  }, [isOpen]);

  const accounts = (data?.crewMembers ?? []).filter((account) => account.role !== 'admin');

  const loadMore = async () => {
    setLoadingMore(true);
    setActionError(null);
    try {
      const loadedCount = data?.crewMembers.length ?? 0;
      const next = await fetchMore({
        variables: { limit: 100, offset: loadedCount },
        updateQuery: (previous, { fetchMoreResult }) => ({
          crewMembers: [...previous.crewMembers, ...fetchMoreResult.crewMembers],
        }),
      });
      setHasMore(next.data.crewMembers.length === 100);
    } catch (failure) {
      setActionError(failure instanceof Error ? failure.message : 'Could not load more accounts');
    } finally {
      setLoadingMore(false);
    }
  };

  const updateRole = async (account: Account) => {
    setChangingId(account.id);
    setActionError(null);
    try {
      await setStaffRole({ variables: { userId: account.id, enabled: account.role !== 'staff' } });
      await refetch();
    } catch (failure) {
      setActionError(failure instanceof Error ? failure.message : 'Could not update this account');
    } finally {
      setChangingId(null);
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
          {hasMore && (data?.crewMembers.length ?? 0) === 100 && <button type="button" onClick={() => void loadMore()} disabled={loadingMore} className="min-h-11 w-full rounded-lg border border-border-strong bg-surface px-4 text-sm font-semibold text-secondary hover:bg-surface-raised focus-visible:ring-2 focus-visible:ring-focus disabled:opacity-50">{loadingMore ? 'Loading…' : 'Load more accounts'}</button>}
        </div>
      </motion.div>
    </div>}
    </AnimatePresence>
  );
};
