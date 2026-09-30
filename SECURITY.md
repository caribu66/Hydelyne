# Security policy

Manifest processes sensitive personal, identity, employment, and compliance
data. Please do not disclose security findings in a public issue or include
real customer data in a report.

## Reporting a vulnerability

Use GitHub's private vulnerability reporting or Security Advisory workflow for
this repository. If that is unavailable, contact the repository maintainers
through the organization's private engineering channel and include:

- a concise description and affected component;
- reproducible steps or a minimal proof of concept;
- the security impact and likely data exposure;
- the first known affected commit or release, if available; and
- a safe contact for follow-up.

Please allow maintainers reasonable time to validate and remediate a report
before public disclosure. Do not test against production, real user accounts,
live Dropbox content, or data belonging to another person.

## Secret exposure

If a credential, token, or private document is exposed, treat it as
compromised immediately: revoke or rotate it, preserve only the minimum
diagnostic evidence, and report the incident privately. See
`SECRET_ROTATION.md` for the supported rotation procedures.

## Scope

The supported security boundary is the backend API and its worker/provider
integrations. Frontend-only issues are still welcome when they can expose
data, bypass a workflow, or weaken authorization assumptions.
