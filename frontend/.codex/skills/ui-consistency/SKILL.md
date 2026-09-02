---
name: ui-consistency
description: Audit and improve the Hydenlyne frontend for design-token consistency, accessibility, responsive behavior, and complete interaction states.
---

# UI consistency

Use this skill for frontend UI reviews, UI bug fixes, and visual-system changes in the Hydenlyne repository.

## Required context

Read `AGENTS.md`, `docs/ui/design-tokens.md`, `docs/ui/component-rules.md`, and `docs/ui/accessibility.md` before editing.

## Audit scope

Inspect the affected flow and shared components for:

- token drift in color, type, spacing, radius, and motion
- semantic HTML and keyboard interaction
- accessible names, focus visibility, dialog behavior, and live regions
- dark/light theme parity
- responsive behavior at 375px, 768px, 1024px, and 1440px
- loading, empty, error, and success states
- consistent terminology and action hierarchy

## Editing policy

- Prefer existing components and tokens.
- Make the smallest coherent change that fixes the finding.
- Do not redesign unrelated screens.
- Do not add a one-off value when an existing token or primitive is appropriate.
- Preserve existing product behavior unless the user requests a behavior change.

## Modes

For audit requests, do not edit until findings are reported or the user explicitly asks for fixes.

For fix requests, address P0/P1 issues first, then run lint, build, `npm run ui:audit`, and `git diff --check`.

## Output

Return:

1. Status: PASS or FAIL
2. Findings grouped by severity with file references
3. Files changed and behavior changes
4. Verification results
5. Remaining risks or manual checks
