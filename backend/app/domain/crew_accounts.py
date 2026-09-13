"""Pure rules for distinguishing contractor profiles from login accounts."""

from __future__ import annotations


def is_contractor_profile(profile: object) -> bool:
    """Return whether a row is eligible for contractor-facing workflows."""
    return (
        getattr(profile, "password_hash", None) is None
        and getattr(profile, "role", None) not in {"staff", "admin"}
    )
