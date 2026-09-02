import { FC, useRef } from 'react';
import { createPortal } from 'react-dom';
import { AlertTriangle } from 'lucide-react';
import { useAccessibleDialog } from '../hooks/useAccessibleDialog';
import { Button, DialogSurface } from './ui';

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
      <DialogSurface
        ref={dialogRef}
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="confirm-dialog-title"
        aria-describedby="confirm-dialog-description"
        className="ui-surface-enter w-full max-w-md p-5 shadow-2xl"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex items-start gap-3">
          <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-warning" aria-hidden="true" />
          <div>
            <h2 id="confirm-dialog-title" className="text-base font-semibold text-primary">{title}</h2>
            <p id="confirm-dialog-description" className="mt-1 text-sm leading-5 text-secondary">{description}</p>
          </div>
        </div>
        <div className="mt-5 flex justify-end gap-2">
          <Button onClick={onCancel}>
            Cancel
          </Button>
          <Button onClick={onConfirm} variant="danger">
            {confirmLabel}
          </Button>
        </div>
      </DialogSurface>
    </div>,
    document.body,
  );
};
