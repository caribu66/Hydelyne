import React from 'react';
import { UserProfile } from '../types';
import { motion, AnimatePresence } from 'motion/react';
import { Scale, X, ArrowRight, Bookmark } from 'lucide-react';

interface ComparisonBarProps {
  compareProfiles: UserProfile[];
  onOpenCompareModal: () => void;
  onClearCompare: () => void;
  onRemoveProfile: (id: string) => void;
}

export const ComparisonBar: React.FC<ComparisonBarProps> = ({
  compareProfiles,
  onOpenCompareModal,
  onClearCompare,
  onRemoveProfile,
}) => {
  if (compareProfiles.length === 0) return null;

  return (
    <AnimatePresence>
      <motion.div
        initial={{ y: 80, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        exit={{ y: 80, opacity: 0 }}
        className="fixed bottom-5 left-1/2 -translate-x-1/2 z-40 max-w-xl w-[92%] sm:w-auto"
      >
        <div className="flex items-center justify-between gap-3 sm:gap-5 px-4 py-2.5 rounded-2xl bg-zinc-900/95 border border-zinc-750 shadow-2xl backdrop-blur-lg">
          {/* Avatar stack & Count */}
          <div className="flex items-center gap-3">
            <div className="flex -space-x-2 overflow-hidden">
              {compareProfiles.map((p) => (
                <div key={p.id} className="relative group">
                  <img
                    src={p.avatar}
                    alt={p.name}
                    className="w-8 h-8 rounded-full object-cover border-2 border-zinc-900 shrink-0"
                  />
                  <button
                    type="button"
                    onClick={() => onRemoveProfile(p.id)}
                    className="absolute -top-1 -right-1 w-3.5 h-3.5 bg-zinc-800 hover:bg-red-500 text-white rounded-full flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity"
                    title={`Remove ${p.name}`}
                  >
                    <X className="w-2.5 h-2.5" />
                  </button>
                </div>
              ))}
            </div>

            <div>
              <span className="text-xs font-semibold text-zinc-100 block">
                {compareProfiles.length} Specialist{compareProfiles.length === 1 ? '' : 's'} Selected
              </span>
              <span className="text-[10px] text-zinc-400 font-mono">
                {compareProfiles.length < 2 ? 'Select 1 more to compare' : 'Ready for side-by-side analysis'}
              </span>
            </div>
          </div>

          {/* Action CTAs */}
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={onClearCompare}
              className="px-2.5 py-1.5 text-xs text-zinc-400 hover:text-zinc-200 transition-colors cursor-pointer"
            >
              Clear
            </button>

            <button
              type="button"
              onClick={onOpenCompareModal}
              disabled={compareProfiles.length < 1}
              className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white font-medium text-xs transition-all shadow-xs cursor-pointer"
            >
              <Scale className="w-3.5 h-3.5" />
              <span>Compare Matrix</span>
              <ArrowRight className="w-3 h-3 ml-0.5" />
            </button>
          </div>
        </div>
      </motion.div>
    </AnimatePresence>
  );
};
