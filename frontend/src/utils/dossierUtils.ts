export function visibleDossierItems<T>(items: readonly T[], isExpanded: boolean, initialItems: number): readonly T[] {
  return isExpanded || items.length <= initialItems ? items : items.slice(0, initialItems);
}
