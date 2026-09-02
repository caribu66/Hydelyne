# Hydenlyne UI design tokens

Hydenlyne uses a restrained monochrome workspace theme. Components consume semantic roles from `src/index.css`; they do not select Tailwind palette colors directly. Dark is the default and light is an equal, independently defined theme.

## Color roles

| Role | Purpose |
| --- | --- |
| `canvas` | Application background |
| `surface` | Controls, cards, dialogs, and panels |
| `surface-raised` | Hovered or elevated content |
| `surface-selected` | Selected neutral content |
| `border-subtle` / `border-strong` | Default and emphasized separation |
| `primary` / `secondary` / `muted` | Text hierarchy |
| `action` / `action-hover` / `on-action` | Primary monochrome actions |
| `accent` / `accent-soft` | Verification, selection, and quiet emphasis |
| `focus` | Keyboard focus and interactive chart emphasis |
| `positive`, `warning`, `danger` | Semantic status foregrounds |
| `*-soft` / `*-border` | Semantic status surfaces and borders |

Literal colors and raw palette utilities are prohibited in feature components and checked by `npm run ui:audit:strict`.

## Typography

- System sans-serif is the product typeface; no remote font request is required.
- Page title: 32–44px; section title: 18–24px; card title: 15–18px.
- Body and controls: 14–16px.
- Metadata: 12–13px and never used for an essential action or value.
- Monospace is limited to identifiers, keyboard shortcuts, compact numeric data, and operational metadata.

## Shape and spacing

- Page maximum: 1280px.
- Spacing follows 4, 8, 12, 16, 24, 32, and 48px increments.
- Controls: 10px radius and at least 44px high.
- Cards and panels: 14px radius.
- Dialogs and primary composed surfaces: 14–16px radius.
- Shadows are restrained and only communicate elevation.

## Components and motion

- Prefer the typed primitives in `src/components/ui.tsx`: `Button`, `IconButton`, `Field`, `Surface`, `SectionHeading`, and `StatusMessage`.
- Badges use neutral, accent, or semantic status roles. Search matches use the theme-aware `search-highlight` role.
- Transitions are short and purposeful. Every animation is disabled by the global reduced-motion rule.
