import { ReactNode, useId, useState } from 'react';
import { visibleDossierItems } from '../utils/dossierUtils';

interface DossierCollectionProps<T> {
  items: readonly T[];
  itemLabel: string;
  initialItems?: number;
  renderItems: (items: readonly T[]) => ReactNode;
}

/** Keeps lengthy dossier lists scannable while retaining every record on demand. */
export function DossierCollection<T>({
  items,
  itemLabel,
  initialItems = 6,
  renderItems,
}: DossierCollectionProps<T>) {
  const [isExpanded, setIsExpanded] = useState(false);
  const contentId = useId();
  const needsDisclosure = items.length > initialItems;
  const visibleItems = visibleDossierItems(items, isExpanded, initialItems);
  const remainingItems = items.length - initialItems;

  return (
    <div id={contentId} className="space-y-2">
      {renderItems(visibleItems)}
      {needsDisclosure && (
        <button
          type="button"
          aria-expanded={isExpanded}
          aria-controls={contentId}
          onClick={() => setIsExpanded((expanded) => !expanded)}
          className="min-h-11 cursor-pointer rounded-[10px] border border-border-subtle bg-surface-raised px-3 text-xs font-semibold text-accent transition-colors hover:bg-accent-soft/60 focus:outline-hidden focus:ring-2 focus:ring-focus"
        >
          {isExpanded ? `Show fewer ${itemLabel}` : `Show ${remainingItems} more ${itemLabel}`}
        </button>
      )}
    </div>
  );
}
