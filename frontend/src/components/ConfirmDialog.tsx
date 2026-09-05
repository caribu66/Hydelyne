import { FC, useRef } from 'react';
import { createPortal } from 'react-dom';
import { motion, AnimatePresence } from 'motion/react';
import { AlertTriangle } from 'lucide-react';
import { useAccessibleDialog } from '../hooks/useAccessibleDialog';
import { Button } from './ui';

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

  return createPortal(
    <AnimatePresence>
      {open && (
        <div className="fixed inset-0 z-[120] flex items-center justify-center p-4">
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.18 }}
            className="fixed inset-0 bg-canvas/80 backdrop-blur-xs"
            onClick={onCancel}
          />
          <motion.div
            ref={dialogRef}
            initial={{ opacity: 0, scale: 0.96, y: 8 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.96, y: 8 }}
            transition={{ duration: 0.18, ease: [0.22, 1, 0.36, 1] }}
            role="alertdialog"
            aria-modal="true"
            aria-labelledby="confirm-dialog-title"
            aria-describedby="confirm-dialog-description"
            className="relative z-10 w-full max-w-md rounded-[14px] border border-border-subtle bg-surface p-5 sm:p-6 shadow-2xl text-primary"
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
          </motion.div>
        </div>
      )}
    </AnimatePresence>,
    document.body,
  );
};
