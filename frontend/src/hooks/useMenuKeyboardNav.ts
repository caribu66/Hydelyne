import { RefObject, useEffect } from 'react';

/**
 * Click-outside, Escape-to-close-and-refocus-trigger, and arrow/Home/End
 * roving focus among `[role="menuitem"]` children — the interaction
 * contract every dropdown/overflow menu in this app shares.
 */
export function useMenuKeyboardNav<T extends HTMLElement = HTMLElement>(
  open: boolean,
  menuRef: RefObject<T | null>,
  triggerRef: RefObject<HTMLElement | null>,
  onClose: () => void,
  autoFocusFirstItem = false,
) {
  useEffect(() => {
    if (!open) return;

    const handlePointerDown = (event: PointerEvent) => {
      if (!menuRef.current?.contains(event.target as Node)) onClose();
    };
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        onClose();
        triggerRef.current?.focus();
        return;
      }
      if (!['ArrowDown', 'ArrowUp', 'Home', 'End'].includes(event.key)) return;
      const items = Array.from(
        menuRef.current?.querySelectorAll<HTMLButtonElement>('[role="menuitem"]') ?? [],
      );
      if (items.length === 0) return;
      event.preventDefault();
      const currentIndex = items.indexOf(document.activeElement as HTMLButtonElement);
      const nextIndex =
        event.key === 'Home'
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
    if (autoFocusFirstItem) {
      requestAnimationFrame(() =>
        menuRef.current?.querySelector<HTMLButtonElement>('[role="menuitem"]')?.focus(),
      );
    }
    return () => {
      document.removeEventListener('pointerdown', handlePointerDown);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [open, menuRef, triggerRef, onClose, autoFocusFirstItem]);
}
