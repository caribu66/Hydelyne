import { FC, useRef } from 'react';
import { createPortal } from 'react-dom';
import { AlertTriangle } from 'lucide-react';
import { useAccessibleDialog } from '../hooks/useAccessibleDialog';

interface ConfirmDialogProps {
  open: boolean;
  title: string;
  description: string;
  confirmLabel: string;
  onConfirm: () => void;
  onCancel: () => void;
}

export const ConfirmDialog: FC<ConfirmDialogProps> = ({
  open,
  title,
  description,
  confirmLabel,
  onConfirm,
  onCancel,
}) => {
  const dialogRef = useRef<HTMLDivElement>(null);
  useAccessibleDialog(open, dialogRef, onCancel);

  if (!open) return null;

  return createPortal(
    <div className="ui-overlay-enter fixed inset-0 z-[120] flex items-center justify-center bg-black/80 p-4" onClick={onCancel}>
      <div
        ref={dialogRef}
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="confirm-dialog-title"
        aria-describedby="confirm-dialog-description"
        className="ui-surface-enter w-full max-w-md rounded-2xl border border-zinc-700 bg-zinc-900 p-5 shadow-2xl"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex items-start gap-3">
          <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-amber-400" aria-hidden="true" />
          <div>
            <h2 id="confirm-dialog-title" className="text-sm font-semibold text-zinc-100">{title}</h2>
            <p id="confirm-dialog-description" className="mt-1 text-xs leading-5 text-zinc-400">{description}</p>
          </div>
        </div>
        <div className="mt-5 flex justify-end gap-2">
          <button type="button" onClick={onCancel} className="min-h-11 rounded-xl bg-zinc-800 px-4 py-2 text-xs font-medium text-zinc-200 hover:bg-zinc-700">
            Cancel
          </button>
          <button type="button" onClick={onConfirm} className="min-h-11 rounded-xl bg-rose-600 px-4 py-2 text-xs font-semibold text-white hover:bg-rose-500">
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>,
    document.body,
  );
};
