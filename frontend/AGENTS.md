# Hydenlyne frontend rules

Use the `ui-consistency` skill for substantial frontend UI work and reviews.

Read the workspace-root `AGENTS.md`, `docs/CHANGELOG.md`, `docs/ARCHITECTURE.md`,
and `docs/ENGINEERING_STANDARDS.md` before changing frontend behavior. This
directory is part of the root monorepo (ADR 0001) — one Git status, one commit
history, shared with the backend.

## Frontend architecture

- Code must always be **clean, efficient, styled, modular, and maintainable**:
  - **Clean**: Clear semantic JSX, well-named hooks and helpers, self-explanatory props, and zero unused code.
  - **Efficient & Lightweight**: Stay light. Zero bloat, no oversized dependencies, lean bundle sizes, and minimal DOM depth. Profile re-renders, use memoization deliberately where beneficial, avoid layout shift, and clean up listeners/timers.
  - **Debt-Resistant**: Actively prevent technical debt. Avoid quick hacks, speculative abstractions, duplicated styling, or unmanaged component state. Fix root causes rather than masking symptoms.
  - **Styled**: 100% adherence to design system tokens (`bg-surface`, `border-border-subtle`, `text-primary`, etc.); avoid arbitrary colors and inconsistent spacing.
  - **Modular**: Break complex views into single-purpose components and reusable hooks (e.g. state management, keyboard navigation, dialogs).
  - **Maintainable**: Strict typing, zero unchecked assumptions, clear prop interfaces, and tests for business utilities and critical flows.
- `src/components/` owns presentational and composed UI surfaces. Extract a
  focused component or hook when a file mixes several workflows.
- `src/hooks/` owns reusable interaction and server-state orchestration.
- `src/lib/` owns typed API clients, GraphQL operations, and boundary mapping.
- `src/utils/` owns pure deterministic functions and should have unit tests.
- `src/types.ts` describes frontend domain/view types; it must remain aligned
  with the GraphQL contract until generated schema types replace it.
- Keep authorization enforcement on the backend. Frontend guards improve UX
  but are never a security boundary.
- Do not call PostgreSQL, Redis, Meilisearch, Qdrant, Ollama, Dropbox, or Gemini
  directly from UI code. All data/provider access goes through an authorized
  backend contract.
- Do not add another global state mechanism without an ADR. Prefer local state,
  focused hooks, Apollo cache for server state, and URL state for shareable
  search/filter state.
- Do not ship mock profiles or placeholder fallbacks in production data paths.
- Async effects must handle cancellation/stale responses and expose loading,
  empty, error, and success states.
- Do not use `any` to bypass a type-design problem. Narrow unknown boundary
  data and model component props explicitly. This is enforced, not advisory —
  `tsconfig.json` has `strict: true` plus `noUncheckedIndexedAccess`, and
  `@typescript-eslint/no-explicit-any` is a blocking ESLint error. See
  `docs/ENGINEERING_STANDARDS.md` § Type safety for the full any/cast/ignore
  policy, including when `@types/<package>` should exist and doesn't (check
  before assuming a library is untyped — most current ones ship real types).
- A non-null assertion (`!`) needs a one-line comment stating the invariant
  that makes it safe (e.g. "guarded by the length check above"); it's an
  ESLint warning, not an error, specifically so it stays visible in review
  instead of silently multiplying.

## Product UI contract

- **Strict Theme & Design Consistency (Buttons, Windows, Fonts, Modals)**:
  - **Buttons**: Every button must follow the design token hierarchy: primary (`bg-action text-on-action hover:bg-action-hover`), secondary (`bg-surface border border-border-subtle hover:bg-surface-raised text-secondary hover:text-primary`), or accent (`bg-accent-soft text-accent hover:border-border-strong`). Radii must be standard (`rounded-lg` or `rounded-full`), touch heights minimum 44px for click targets, with visible ring focus states (`focus-visible:ring-2 focus-visible:ring-focus`).
  - **Windows & Panels**: Workspace windows, sidebars, panes, and cards must strictly use surface tokens (`bg-canvas`, `bg-surface`, `bg-surface-raised`), standardized border contrast (`border-border-subtle`, `border-border-strong`), and uniform rounded corners (`rounded-[14px]`). No mismatched dropshadows or ad-hoc background colors.
  - **Fonts & Typography**: Strict typographic scale and font families (`font-sans` for labels/body text, `font-mono` for metadata/codes/metrics/rates/shortcuts). Maintain hierarchy: Primary headers (`text-primary font-semibold`), subtext/labels (`text-secondary`), supporting metadata (`text-muted`).
  - **Modals & Dialogs**: All modals must share the same architectural shell: backdrop blur (`bg-canvas/80 backdrop-blur-xs`), card surface (`bg-surface border border-border-subtle rounded-[14px] shadow-2xl p-5 sm:p-6`), header with icon container + title + close `X` button, scrollable body, and action footer.
  - **Dual-Theme Fidelity**: Never test or ship a surface in one theme only. Every button, input, badge, border, modal, and window must look deliberate, crisp, and high-contrast in BOTH dark and light themes.
- Visual harmony is an acceptance criterion, not cosmetic polish. Before
  shipping a UI change, compare the edited surface with its adjacent reading
  surfaces and reuse the same hierarchy: semantic tokens, spacing rhythm,
  corner treatment, control height, typography scale, disclosure behavior,
  and empty/loading states. Do not introduce a one-off visual pattern when an
  established one can express the interaction.
- Reuse existing components and the documented design tokens before creating new patterns.
- Keep terminology consistent: use “specialist”, “shortlist”, “compare”, and “mobilization request”.
- Support dark and light themes for every new surface.
- Interactive controls must be keyboard accessible, have visible focus, and use semantic HTML.
- Icon-only controls require an accessible name via `aria-label`.
- Dialogs must have an accessible name, close on Escape, trap focus, restore focus, and lock page scroll.
- Use a minimum 14px body size unless the smaller size is intentional metadata.
- Use a minimum 44px touch target for primary interactive controls.
- Respect `prefers-reduced-motion`.
- Provide loading, empty, error, and success states for async workflows.

## Verification

Before completing UI work, run:

```bash
npm run lint
npm run test
npm run build
npm run ui:audit:strict
git diff --check
```

Run `npm run test:e2e:ci` for changes to authentication, navigation, dialogs,
documents, search, shortlist/compare, responsive layout, or other critical user
flows. For responsive changes, verify 375px, 768px, 1024px, and 1440px widths.

Review build warnings and UI-audit warnings; a zero exit code does not mean a
warning was approved. Do not update visual snapshots until the rendered change
has been inspected and confirmed intentional.
