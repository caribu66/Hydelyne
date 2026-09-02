import { FC, useEffect, useId, useRef, useState } from 'react';
import { Bookmark, BookmarkCheck, Check, Copy, Ellipsis, Scale, Send } from 'lucide-react';
import { UserProfile } from '../types';

interface SpecialistActionsMenuProps {
  profile: UserProfile;
  isBookmarked: boolean;
  isCompared: boolean;
  copied?: boolean;
  onToggleBookmark: () => void;
  onToggleCompare: () => void;
  onCopyEmail?: () => void;
  onRequestMobilization?: () => void;
}

export const SpecialistActionsMenu: FC<SpecialistActionsMenuProps> = ({
  profile,
  isBookmarked,
  isCompared,
  copied = false,
  onToggleBookmark,
  onToggleCompare,
  onCopyEmail,
  onRequestMobilization,
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const menuId = useId();
  const rootRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!isOpen) return;

    const handlePointerDown = (event: PointerEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) setIsOpen(false);
    };
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setIsOpen(false);
        triggerRef.current?.focus();
        return;
      }
      if (!['ArrowDown', 'ArrowUp', 'Home', 'End'].includes(event.key)) return;
      const items = Array.from(rootRef.current?.querySelectorAll('[role="menuitem"]') ?? []) as HTMLButtonElement[];
      if (items.length === 0) return;
      event.preventDefault();
      const currentIndex = items.indexOf(document.activeElement as HTMLButtonElement);
      const nextIndex = event.key === 'Home'
        ? 0
        : event.key === 'End'
          ? items.length - 1
          : event.key === 'ArrowDown'
            ? (currentIndex + 1) % items.length
            : (currentIndex - 1 + items.length) % items.length;
      items[nextIndex]?.focus();
    };

    document.addEventListener('pointerdown', handlePointerDown);
    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('pointerdown', handlePointerDown);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [isOpen]);

  useEffect(() => {
    if (isOpen) {
      requestAnimationFrame(() => rootRef.current?.querySelector<HTMLButtonElement>('[role="menuitem"]')?.focus());
    }
  }, [isOpen]);

  const runAction = (action: () => void) => {
    action();
    setIsOpen(false);
    triggerRef.current?.focus();
  };

  const itemClass = 'flex min-h-11 w-full items-center gap-3 rounded-lg px-3 text-left text-sm text-secondary transition-colors hover:bg-surface-raised hover:text-primary focus-visible:bg-surface-raised focus-visible:text-primary';

  return (
    <div ref={rootRef} className="relative shrink-0">
      <button
        ref={triggerRef}
        type="button"
        aria-label={`More actions for ${profile.name}`}
        aria-haspopup="menu"
        aria-expanded={isOpen}
        aria-controls={isOpen ? menuId : undefined}
        onClick={() => setIsOpen((open) => !open)}
        className={`inline-flex min-h-11 min-w-11 items-center justify-center rounded-[10px] transition-colors ${
          isOpen ? 'bg-surface-raised text-primary' : 'text-muted hover:bg-surface-raised/70 hover:text-primary'
        }`}
      >
        <Ellipsis className="h-4 w-4" aria-hidden="true" />
      </button>

      {isOpen && (
        <div
          id={menuId}
          role="menu"
          aria-label={`Actions for ${profile.name}`}
          className="absolute right-0 top-12 z-40 w-56 rounded-[14px] border border-border-strong/80 bg-surface/95 p-1.5 shadow-2xl shadow-black/40 backdrop-blur-xl"
        >
          <button type="button" role="menuitem" onClick={() => runAction(onToggleBookmark)} className={itemClass}>
            {isBookmarked ? <BookmarkCheck className="h-4 w-4 text-accent" /> : <Bookmark className="h-4 w-4" />}
            {isBookmarked ? 'Remove from shortlist' : 'Save to shortlist'}
          </button>
          <button type="button" role="menuitem" onClick={() => runAction(onToggleCompare)} className={itemClass}>
            <Scale className={`h-4 w-4 ${isCompared ? 'text-accent' : ''}`} />
            {isCompared ? 'Remove from compare' : 'Add to compare'}
          </button>
          {onCopyEmail && (
            <button type="button" role="menuitem" onClick={() => runAction(onCopyEmail)} className={itemClass}>
              {copied ? <Check className="h-4 w-4 text-positive" /> : <Copy className="h-4 w-4" />}
              {copied ? 'Email copied' : 'Copy email'}
            </button>
          )}
          {onRequestMobilization && (
            <button type="button" role="menuitem" onClick={() => runAction(onRequestMobilization)} className={`${itemClass} text-accent`}>
              <Send className="h-4 w-4" />
              Request mobilization
            </button>
          )}
        </div>
      )}
    </div>
  );
};
