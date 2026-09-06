# ADR 0007: Consultant-to-Vessel Campaign Assignments

- Status: accepted
- Date: 2026-09-06
- Owners: backend + frontend + operations maintainers
- Supersedes: none; implements mobilization intelligence outlined in `docs/CHANGELOG.md`

## Context

Hydenlyne operates an offshore specialist management platform. Prior to this decision:
1. Specialists (`crew_members`) held an unmanaged `availability_status` ("available", "on_assignment", "unavailable") that required manual updates.
2. Projects (`projects`) held assignments as a loose, unindexed JSON string list (`Project.crew_assigned = ["crew-1", "crew-2"]`). There were no foreign key constraints, no role tracking on board, no mobilization dates, and no link to maritime vessels.
3. Vessels were searched ephemerally via VesselAPI proxy (`vessel_api.py`), with no persistent presence in PostgreSQL.
4. The mobilization UI (`MobilizationInquiryModal.tsx`) generated mock client references (`HYD-MOB-2026-XXXX`) via `setTimeout` without writing to the database.
5. There was no way to query a vessel's active crew roster or detect double-booking of specialists across overlapping offshore campaigns.

## Decision

1. **Persistent PostgreSQL `vessels` Table**:
   Store core maritime identity in PostgreSQL (`imo` primary key, `name`, `mmsi`, `callsign`, `vessel_type`, `flag`, `length`, `width`, `year_built`). When a vessel is assigned, its record is upserted locally from verified VesselAPI metadata.

2. **Relational `campaign_assignments` Table**:
   Create a first-class join entity linking `crew_member_id` (FK to `crew_members.id`), `vessel_imo` (FK to `vessels.imo`), and optional `project_id` (FK to `projects.id`), with:
   - `role_on_board`: string (e.g., Party Chief, Lead Geophysicist, Client Representative)
   - `start_date` and `end_date`: campaign mobilization window
   - `status`: enum (`proposed`, `confirmed`, `on_board`, `completed`, `cancelled`)
   - `agreed_day_rate`: optional commercial rate (classified C3 / admin-only under ADR 0005)
   - `notes`: operational instructions

3. **Automated Lifecycle Synchronization**:
   - Creating or confirming an assignment automatically updates the consultant's `availability_status` to `on_assignment` when active, and resets it to `available` upon completion if no other active assignment exists.
   - Schedule overlap detection prevents double-booking a consultant on conflicting dates.
   - Compliance pre-check verifies that the consultant's offshore certifications (BOSIET, Medical) remain valid through the campaign's `end_date`.

4. **Tiered Access & Data Classification (ADR 0005 Integration)**:
   - Vessel specifications are C1 (recruiter-safe).
   - Assignment roster and operational roles are C2 (staff/admin).
   - Commercial agreed day rates are C3 (admin only).

## Alternatives considered

- *Keep JSON array on Project*: Retaining `Project.crew_assigned` as a JSON array cannot enforce referential integrity, date-range exclusion, or direct vessel-to-crew queries.
- *Purely ephemeral assignments in Redis*: Would be disposable and lose historical mobilization tracking and compliance audits required by maritime energy operators.

## Consequences

- **Benefits**:
  - Full traceability: operators can inspect live vessel rosters and historical campaign deployments.
  - Prevention of double-booking and automated crew readiness metrics.
  - Replaces mock UI modal with real transactional mutation and toast notifications.
- **Costs**:
  - Schema migration (`016_vessel_assignments`).
  - Added validation logic when creating and transitioning assignments.

## Migration and rollback

- Alembic migration `016_vessel_assignments.py` with non-destructive upgrade and clean downgrade.
- Existing projects and crew members remain unaffected; legacy `Project.crew_assigned` column is preserved for backwards compatibility.

## Validation

- Pytest suite `backend/tests/test_campaign_assignments.py` testing creation, conflict detection, compliance expiration validation, and availability state synchronization.
- Frontend queries, mutations, and Playwright verification.
