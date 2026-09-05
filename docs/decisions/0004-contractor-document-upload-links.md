# 0004 — Contractor document upload links

Status: accepted, 2026-09-05.

## Context

Contractors commonly deliver evidence through WhatsApp. This leaves operations
staff to download, rename, find the right contractor, upload, and then review
each file manually. The company does not currently operate a Microsoft 365
mailbox integration.

## Decision

Hydenlyne issues staff-created, expiring bearer upload links. A contractor can
upload directly without a Hydenlyne account. The raw token is returned only at
request creation and PostgreSQL stores an HMAC hash. A successful upload enters
the existing document storage, validation, extraction, and review workflow and
also creates a durable staff review-queue item.

The public endpoint returns no contractor identity or document history. Files
are not trusted or verified merely because they arrived through a valid link.

## Consequences

- The first release needs no email provider, mailbox, or personal inbox access.
- Links are bearer credentials: staff must use the normal approved channels to
  share them, and the 14-day default limits exposure.
- Microsoft Graph or another inbound-mail adapter may later create the same
  document request/review records; it must not duplicate document processing.
- The database migration is additive. Rolling back the feature disables new
  links but does not remove already stored documents or their audit trail.
