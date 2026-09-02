# ADR 0001: Repository Topology — True Monorepo

- Status: accepted
- Date: 2026-09-02
- Owners: backend + frontend maintainers
- Supersedes: implicit split between `caribu66/hydenlyne-crew-dms` (root) and
  `caribu66/Hydelyne` (`frontend/`)

## Context

`frontend/` was a separate Git repository rooted at the `frontend/` directory
of the working tree, with its own history. Root CI referenced `./frontend` via
`working-directory: ./frontend` even though the root `.gitignore` excluded the
directory on a clean clone. The frontend's CI path resolved only because the
checkout already contained the standalone frontend history.

The split forced every change that touched the contract (e.g. `types.ts`,
GraphQL schema, auth flow) into two commits in two repositories with no
atomic merge and no shared CI gate. A change in the root that broke a frontend
import would not be caught until the next frontend release.

## Decision

Adopt a true monorepo at the root:

- `frontend/.git/` is removed; `frontend/` becomes a directory of the root
  repository.
- `frontend/` is removed from the root `.gitignore`.
- Root `.github/workflows/ci.yml` covers backend and frontend in separate
  jobs under the same checkout, with `working-directory: ./backend` and
  `working-directory: ./frontend` respectively.

No frontend history import. The audit remediation plan treats the frontend as
a clean add; we accept losing the standalone history in exchange for atomic
cross-stack commits and a single CI pipeline.

## Alternatives considered

- **Subtree merge (`git subtree add`)**: preserves frontend history but
  carries its own operational cost (rewriting `.gitignore`, periodic `subtree
  pull`). Rejected as overkill — no concrete need for history archaeology.
- **Keep two repos with a shared API package**: forces a third published
  artifact and tighter coupling between release cadences. Rejected because
  the audit's main motivator is "broken CI on a clean checkout", which a true
  monorepo fixes directly.
- **Polyrepo with a release tooling layer**: introduces new infrastructure
  (changesets, semantic-release). Rejected; the project is small enough that
  one CI workflow is sufficient.

## Consequences

- One commit can touch backend + frontend + docs atomically.
- CI becomes the single source of truth for both stacks.
- The frontend can no longer be released independently of the backend, but
  independent deploys were already constrained by the GraphQL contract.
- `git log -- frontend/` starts fresh; archaeology of pre-merge frontend work
  must use the old standalone repo's reflog if needed.

## Migration and rollback

- Forward: `rm -rf frontend/.git`, edit `.gitignore`, `git add frontend/`.
  No data migration.
- Rollback: re-clone the standalone frontend repo into `frontend/` if a hard
  revert is required. The frontend is fully reproducible from
  `package.json` + `package-lock.json` once merged.

## Validation

- `git ls-files | grep "^frontend/" | wc -l` is non-zero.
- `git check-ignore frontend/package.json` exits non-zero.
- Root CI's `frontend` job runs `npm ci`, `npm run lint`, `npm run test`,
  `npm run build`, `npm run ui:audit:strict`, and `npm audit` against the
  merged frontend on a clean checkout.