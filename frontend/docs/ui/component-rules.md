# Hydenlyne component rules

## Language

- Product name: “Hydenlyne”.
- People in the network are “specialists”.
- Saved specialists belong to the “shortlist”.
- Side-by-side review is “compare”.
- Deployment contact is a “mobilization request”.
- Use concise sentence case for labels and messages.

## Controls

- Start with `Button`, `IconButton`, or `Field` from the shared UI module. Add a variant there when a genuinely reusable role is missing.
- Primary actions have text labels. Icon-only controls require an accessible name.
- Toggles use `aria-pressed`; menus and dialogs expose their expanded/open state.
- Focus is visible, touch targets are at least 44px, and state is never communicated through color alone.

## Surfaces and states

- Cards, rows, dialogs, and menus use semantic surface and border roles rather than raw colors.
- Keep the primary row/card action semantic and separate from secondary actions.
- Every data-dependent surface has loading, empty, error, and success states without changing its visual vocabulary.
- Dialogs are named, trap and restore focus, close on Escape when safe, and lock page scroll.

## Responsive workspace

- Mobile uses a single results column and modal dossier navigation.
- Tablet and desktop retain the focused split workspace, with cards and matrix views available from the same toolbar.
- Text and controls remain usable at 200% zoom without horizontal page overflow.
