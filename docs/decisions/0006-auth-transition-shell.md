# ADR 0006: Calm auth transition shell and unified auth state

- Status: accepted
- Date: 2026-09-06
- Owners: Hydenlyne crew
- Supersedes: n/a

## Context

Signing in and signing out currently hard-cuts the workspace. The login modal animates (`LoginPage.tsx:139 AnimatePresence` 200 ms), but the shell behind it does not:

- `frontend/src/hooks/useAuth.ts:15` creates isolated `user/initialized` state per call site. `LoginPage.tsx:24` and `App.tsx:105` each hold a disjoint state machine — sign-in in the modal sets _its_ `user`, `App` waits for `ME_QUERY` `network-only` refetch `App.tsx:1639 void refreshSession()` before `isAuthenticated` flips, producing a delay + snap from `ModernHeroSearch.tsx:143` public hero (`min-h-[calc(100dvh-4rem)]`) to `OperationsHome.tsx:89` (`py-6`).
- The auth gate `App.tsx:430 if (!authInitialized) return … Loading session…` and `main.tsx:32 Suspense fallback Loading workspace…` are two disjoint mounts with no `AnimatePresence`, differing copy, no `motion`.
- The calm states `App.tsx:631 (!isAuthenticated || isSearchActive) ModernHeroSearch` vs `656 !isSearchActive && isAuthenticated OperationsHome` and the active search header `688`/`774` toggle via bare `&&` without `AnimatePresence`; Tailwind `transition-all duration-300` on the wrapper does not animate identity change. Logout `App.tsx:464 handleLogout` clears 12 states + `history.replaceState('/')` synchronously before `await logout()` while `AppMenuDrawer.tsx:70 closeAfter` slides concurrently — background snaps behind the drawer.
- Existing motion is otherwise excellent and token-consistent (`FilterModal.tsx:40`, `LoginPage.tsx:145`, `AppMenuDrawer.tsx:92`, `App.tsx:930`, `Toast.tsx:14`, `index.css:81 --motion-ui-duration`) and should be reused, not replaced.

`frontend/AGENTS.md` warns against adding global state without an ADR; this decision therefore records why a single shared auth state is not new state but a consolidation.

## Decision

1. **Single shared auth state** via a lightweight `AuthContext` provider mounted in `main.tsx` around `<App>`. `useAuth()` becomes a context consumer (back-compatible API). It still drives `ME_QUERY` once, still uses `credentials:'include'` cookie + `apolloClient.clearStore()`, but both modal and shell read/write the same `user/initialized`. Login sets `user` optimistically (already does) and propagates instantly; `refreshSession` remains as background revalidation, not gating UI.
2. **Calm-professional auth shell transition** — wrap the top-level gate and the calm-vs-active workspace in one `AnimatePresence mode="wait" initial={false}` with `motion.div initial {opacity:0,y:8} animate {opacity:1,y:0} exit {opacity:0,y:-6} duration 0.18-0.20 ease [0.22,1,0.36,1]` (`MotionConfig reducedMotion="user"`). No `scale`. Ambient `bg-radial-ambient App.tsx:500` stays mounted; height is not animated via `min-h` — identity fades, not stretched. This mirrors the existing modal/drawer/list/Toast contracts.
3. **Orchestrated sign-in / sign-out**:
   - Sign-in: modal exit 200 ms completes before shell crossfade; no double-loader flash; skeleton `SkeletonResults` appears inside entering container.
   - Sign-out: drawer `x:100% 0.24` completes before workspace purge; heavy clears + `history.replaceState('/')` move to `onExitComplete`; toast `Signed out — workspace cleared` via existing `Toast.tsx:14` motion appears on completion.
4. **OperationsHome stagger** — calm cards (`OperationsGreeting`, `OperationsAttention`, `OperationsMetrics`, `OperationsProjectsPanel`) enter with `staggerChildren 0.04-0.06` reusing list pattern `App.tsx:930`, stays invisible under `prefers-reduced-motion`.

## Alternatives considered

- **Module singleton shared state** (no context, bare `let sharedUser` in `useAuth.ts`): avoids context/ADR but breaks Fast Refresh, is ad-hoc global, and hides dependency — rejected.
- **Keep dual `useAuth()` and just add motion**: would still snap after modal close waiting on `ME_QUERY`; motion alone cannot fix state propagation — rejected.
- **View Transitions API (`document.startViewTransition`)**: browser coverage incomplete, overlaps Framer Motion (`motion` 12.23.24 already in bundle), inconsistent with existing `AnimatePresence` — rejected for this slice (may be additive later).
- **CSS `transition-all` on `min-h`/`height`**: `min-h-[calc(100dvh-4rem)] ↔ 44vh` not interpolable because element remounts; `motion.layout` considered but rejected for shell — calm fade/y is intended (leaner, no layout thrash on mobile).

## Consequences

- Benefits: instant-feeling sign-in (no network wait before shell change), soft sign-out with no snap-behind-drawer, unified source for `isSearchActive` gating (security boundary `ARCHITECTURE.md:169` preserved), motion-consistent with existing modals/drawers.
- Costs: one small context provider + one ADR; negligible bundle delta (motion already loaded, `App` chunk currently 41 KiB gzip).
- Constraints: `AuthContext` is the single owner of auth state — new call sites must consume it, not instantiate isolated `useAuth` state. `MotionConfig reducedMotion="user"` continues to govern all auth motion.
- Security: no transport change; login still sets `hydenlyne_session` cookie `backend/app/graphql/schema.py:527`, logout still `delete_cookie` + `revoke_session_token`, `isSearchActive` remains the single privacy gate.

## Migration and rollback

- Vertical slices: (1) provider, (2) shell presence, (3) choreography, each tested separately.
- Compatibility: `useAuth` public API (`user`, `initialized`, `isAuthenticated`, `login`, `logout`, `refreshSession`, `loggingIn`, `error`) unchanged — callers only change import path.
- Rollback: revert provider import in `main.tsx` + restore original `useAuth.ts` isolated hook; shell falls back to hard `&&` guards — functional, just rough again.
- No migration, no env var.

## Validation

- `npm run lint` (`tsc --noEmit && eslint`), `npm run test` (Vitest incl. `operationsHome.test.ts` 72), `npm run build` budget, `npm run ui:audit:strict` (91 files clean), `npm run test:e2e:ci` (auth-gate, operations-home, authenticated-flow, public-shell). Manual checks at 375/768/1024/1440 dark+light, `prefers-reduced-motion: reduce` disables shell motion as expected.
