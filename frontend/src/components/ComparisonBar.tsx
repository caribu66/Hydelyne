import { FC } from 'react';
import { UserProfile } from '../types';
import { motion, AnimatePresence } from 'motion/react';
import { Scale, X, ArrowRight } from 'lucide-react';

interface ComparisonBarProps {
  compareProfiles: UserProfile[];
  onOpenCompareModal: () => void;
  onClearCompare: () => void;
  onRemoveProfile: (id: string) => void;
}

export const ComparisonBar: FC<ComparisonBarProps> = ({
  compareProfiles,
  onOpenCompareModal,
  onClearCompare,
  onRemoveProfile,
}) => {
  return (
    <AnimatePresence>
      {compareProfiles.length > 0 && (
        <motion.div
          initial={{ y: 80, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          exit={{ y: 80, opacity: 0 }}
          transition={{ duration: 0.2, ease: [0.22, 1, 0.36, 1] }}
          className="fixed bottom-5 left-1/2 -translate-x-1/2 z-40 max-w-xl w-[92%] sm:w-auto"
        >
        <div className="flex items-center justify-between gap-3 sm:gap-5 px-4 py-2.5 rounded-[14px] bg-surface/95 border border-border-strong shadow-2xl backdrop-blur-lg">
          {/* Avatar stack & Count */}
          <div className="flex items-center gap-3">
            <div className="flex -space-x-2 overflow-hidden">
              {compareProfiles.map((p) => (
                <div key={p.id} className="relative group">
                  <img
                    src={p.avatar}
                    alt={p.name}
                    className="w-8 h-8 rounded-full object-cover border-2 border-border-subtle shrink-0"
                  />
                  <button
                    type="button"
                    onClick={() => onRemoveProfile(p.id)}
                    className="absolute -top-2 -right-2 w-6 h-6 bg-surface-raised hover:bg-danger text-on-action rounded-full flex items-center justify-center opacity-100 sm:opacity-0 sm:group-hover:opacity-100 transition-opacity"
                    title={`Remove ${p.name}`}
                    aria-label={`Remove ${p.name} from comparison`}
                  >
                    <X className="w-2.5 h-2.5" />
                  </button>
                </div>
              ))}
            </div>

            <div>
              <span className="text-xs font-semibold text-primary block">
                {compareProfiles.length} contractor{compareProfiles.length === 1 ? '' : 's'} selected
              </span>
              <span className="text-xs text-secondary font-mono">
                {compareProfiles.length < 2 ? 'Select 1 more to compare' : 'Ready for side-by-side analysis'}
              </span>
            </div>
          </div>

          {/* Action CTAs */}
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={onClearCompare}
              className="inline-flex items-center justify-center min-h-9 px-3 rounded-lg text-xs font-medium text-secondary hover:text-primary hover:bg-surface-raised transition-colors cursor-pointer focus:outline-none focus-visible:ring-2 focus-visible:ring-focus"
            >
              Clear
            </button>

            <button
              type="button"
              onClick={onOpenCompareModal}
              className="inline-flex min-h-9 items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-action hover:bg-action-hover text-on-action font-semibold text-xs transition-all shadow-xs cursor-pointer focus:outline-none focus-visible:ring-2 focus-visible:ring-focus"
              title={compareProfiles.length < 2 ? 'Open comparison matrix to add another specialist' : 'Compare specialists side by side'}
            >
              <Scale className="w-3.5 h-3.5 shrink-0" />
              <span>{compareProfiles.length < 2 ? 'Compare (1) · Add more' : `Compare Matrix (${compareProfiles.length})`}</span>
              <ArrowRight className="w-3 h-3 ml-0.5 shrink-0" />
            </button>
          </div>
        </div>
      </motion.div>
    )}
  </AnimatePresence>
  );
};
