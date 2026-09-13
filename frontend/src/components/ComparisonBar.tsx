import { FC } from 'react';
import { UserProfile } from '../types';
import { motion, AnimatePresence } from 'motion/react';
import { Scale, X, ArrowRight, Plus } from 'lucide-react';

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
          transition={{ duration: 0.22, ease: [0.22, 1, 0.36, 1] }}
          className="fixed bottom-5 left-1/2 -translate-x-1/2 z-40 max-w-2xl w-[94%] sm:w-auto"
        >
          <div className="flex flex-col sm:flex-row items-center justify-between gap-3 sm:gap-5 px-4 py-2.5 rounded-[16px] bg-surface/95 border border-border-strong shadow-2xl backdrop-blur-xl">
            {/* Selected Specialist Slots & Prompt */}
            <div className="flex items-center gap-2 overflow-x-auto max-w-full py-0.5 scrollbar-none">
              {compareProfiles.map((p) => (
                <div
                  key={p.id}
                  className="flex items-center gap-2 rounded-xl border border-border-strong/70 bg-surface-raised/70 pl-2 pr-1.5 py-1 shrink-0"
                >
                  <img
                    src={p.avatar}
                    alt={p.name}
                    className="w-7 h-7 rounded-lg object-cover ring-1 ring-border-subtle shrink-0"
                  />
                  <div className="min-w-0 pr-1 text-left">
                    <span className="text-xs font-semibold text-primary block truncate max-w-[100px] sm:max-w-[120px]">
                      {p.name.split(' ')[0]} {p.name.split(' ')[1]?.[0]}.
                    </span>
                    <span className="text-xs text-secondary font-mono block truncate max-w-[100px] sm:max-w-[120px]">
                      {p.dayRate != null ? `£${p.dayRate}/d` : 'Rate on request'}
                    </span>
                  </div>
                  <button
                    type="button"
                    onClick={() => onRemoveProfile(p.id)}
                    className="min-h-7 min-w-7 p-1 rounded-md text-muted hover:text-danger hover:bg-surface-raised transition-colors flex items-center justify-center shrink-0 cursor-pointer"
                    title={`Remove ${p.name}`}
                    aria-label={`Remove ${p.name} from comparison`}
                  >
                    <X className="w-3.5 h-3.5" />
                  </button>
                </div>
              ))}

              {compareProfiles.length === 1 && (
                <div className="hidden sm:flex items-center gap-2 rounded-xl border border-dashed border-border-strong/60 bg-surface/40 px-3 py-2 shrink-0">
                  <div className="w-6 h-6 rounded-lg border border-dashed border-border-strong flex items-center justify-center text-muted">
                    <Plus className="w-3.5 h-3.5" />
                  </div>
                  <span className="text-xs text-muted font-medium">
                    Select 1 more to compare
                  </span>
                </div>
              )}
            </div>

            {/* Action CTAs */}
            <div className="flex items-center gap-2 shrink-0 w-full sm:w-auto justify-end">
              <button
                type="button"
                onClick={onClearCompare}
                className="inline-flex items-center justify-center min-h-11 px-3 rounded-lg text-xs font-medium text-secondary hover:text-primary hover:bg-surface-raised transition-colors cursor-pointer focus:outline-none focus-visible:ring-2 focus-visible:ring-focus"
              >
                Clear
              </button>

              <button
                type="button"
                onClick={onOpenCompareModal}
                className="inline-flex min-h-11 items-center gap-2 px-4 py-2 rounded-xl bg-action hover:bg-action-hover text-on-action font-semibold text-xs transition-all shadow-xs cursor-pointer focus:outline-none focus-visible:ring-2 focus-visible:ring-focus active:scale-98"
                title={compareProfiles.length < 2 ? 'Open comparison matrix to add another specialist' : 'Compare specialists side by side'}
              >
                <Scale className="w-4 h-4 shrink-0" />
                <span>{compareProfiles.length < 2 ? 'Compare Matrix (1)' : `Compare Matrix (${compareProfiles.length})`}</span>
                <ArrowRight className="w-3.5 h-3.5 ml-0.5 shrink-0" />
              </button>
            </div>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
};
