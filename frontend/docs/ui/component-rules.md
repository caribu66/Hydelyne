# Component rules

## Buttons

- Use a text label for primary actions.
- Use `aria-label` for icon-only actions.
- Use `aria-pressed` for toggles such as shortlist, compare, and view mode.
- Include a visible `:focus-visible` state.
- Do not communicate state through color alone.

## Cards and rows

- Make the primary action a semantic button or link.
- Do not use clickable headings or generic divs as controls.
- Keep secondary actions separate from the primary click target.
- Preserve a stable visual height when loading or filtering.

## Dialogs

- Use `role="dialog"` and `aria-modal="true"`.
- Reference a visible heading with `aria-labelledby`.
- Trap focus while open and restore focus when closed.
- Lock document scrolling while open.
- Allow backdrop click and Escape to close unless the workflow is destructive or incomplete.

## States

Every data-dependent surface needs distinct states for loading, empty, error, and success. Do not present unavailable data as an empty search result.
