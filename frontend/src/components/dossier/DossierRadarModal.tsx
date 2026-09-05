import { FC, useRef } from 'react';
import { createPortal } from 'react-dom';
import { motion, AnimatePresence } from 'motion/react';
import { UserProfile } from '../../types';
import { useAccessibleDialog } from '../../hooks/useAccessibleDialog';
import { CandidateSkillRadarChart } from '../CandidateSkillRadarChart';
import { X } from 'lucide-react';

interface DossierRadarModalProps {
  isOpen: boolean;
  onClose: () => void;
  profile: UserProfile;
}

export const DossierRadarModal: FC<DossierRadarModalProps> = ({ isOpen, onClose, profile }) => {
  const radarCloseRef = useRef<HTMLButtonElement>(null);
  const radarDialogRef = useRef<HTMLDivElement>(null);

  useAccessibleDialog(isOpen, radarDialogRef, onClose);

  if (typeof document === 'undefined') return null;

  return createPortal(
    <AnimatePresence>
      {isOpen && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-3 sm:p-6">
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.18 }}
            className="fixed inset-0 bg-canvas/80 backdrop-blur-xs"
            onClick={onClose}
          />
          <motion.div
            ref={radarDialogRef}
            initial={{ opacity: 0, scale: 0.96, y: 8 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.96, y: 8 }}
            transition={{ duration: 0.18, ease: [0.22, 1, 0.36, 1] }}
            className="relative z-10 w-full max-w-4xl max-h-[94vh] overflow-y-auto rounded-[14px] border border-border-strong bg-surface p-4 sm:p-6 shadow-2xl"
            onClick={(event) => event.stopPropagation()}
            role="dialog"
            aria-modal="true"
            aria-label={`${profile.name} skills radar`}
          >
            <div className="mb-3 flex items-center justify-between gap-3">
              <div>
                <h3 className="text-sm font-semibold text-primary">Skills Radar</h3>
                <p className="text-xs text-secondary">{profile.name} · Competency assessment</p>
              </div>
              <button
                type="button"
                onClick={onClose}
                ref={radarCloseRef}
                className="rounded-[10px] bg-surface-raised p-2 text-secondary transition-colors hover:bg-surface-selected hover:text-primary cursor-pointer"
                title="Close skills radar"
                aria-label="Close dialog"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            <CandidateSkillRadarChart profile={profile} size="lg" showLegend={true} />
            <div className="mt-4 rounded-[10px] border border-border-subtle bg-canvas/50 p-4 text-xs text-secondary">
              <span className="mb-1 block font-mono text-xs font-semibold uppercase text-primary">
                Methodology & Assessment Criteria
              </span>
              <p>
                Calculated dynamically from verified offshore track records, certifications, and
                technical proficiencies.
              </p>
            </div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>,
    document.body,
  );
};
