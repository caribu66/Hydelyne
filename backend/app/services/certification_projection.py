"""Helpers for keeping contractor-level certification projections coherent."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.certifications import is_medical_cert_type
from app.domain.crew_accounts import is_contractor_profile
from app.models import Certification, CrewMember


def counts_as_medical_evidence(certification: Certification) -> bool:
    """Return whether a certificate row may populate the deployability projection.

    Administrator-verified evidence always counts. Unverified rows count only
    when backed by a linked source document from the extraction pipeline — a
    bare pending assertion with no evidence must not read as mobilizable.
    Rejected rows never count.
    """
    if certification.status is not None and certification.status == "rejected":
        return False
    if certification.verification_status == "verified":
        return True
    return (
        certification.document_ref is not None and certification.verification_status != "rejected"
    )


async def reconcile_medical_profile(
    session: AsyncSession,
    *,
    crew_id: str,
) -> None:
    """Recompute root medical fields from the current certificate evidence."""
    crew = (
        await session.execute(select(CrewMember).where(CrewMember.id == crew_id).with_for_update())
    ).scalar_one_or_none()
    if crew is None or not is_contractor_profile(crew):
        return

    certifications = await session.execute(
        select(Certification).where(Certification.crew_member_id == crew_id)
    )
    medical_dates = [
        certification.expiry_date
        for certification in certifications.scalars()
        if certification.expiry_date
        and is_medical_cert_type(certification.cert_type)
        and counts_as_medical_evidence(certification)
    ]
    replacement_expiry = max(medical_dates) if medical_dates else None
    crew.medical_expiry = replacement_expiry
    crew.medical_status = (
        ("fit" if replacement_expiry and replacement_expiry >= date.today() else "expired")
        if replacement_expiry
        else None
    )


async def reconcile_medical_profile_after_detachment(
    session: AsyncSession,
    *,
    crew_id: str,
    detached_certification_ids: Iterable[str],
    detached_expiry_dates: Iterable[date | None],
) -> None:
    """Remove stale root medical data when its certificate evidence is detached.

    Certificate extraction maintains ``CrewMember.medical_expiry`` as a
    denormalized convenience field. Detaching the source evidence must either
    select another remaining certificate or clear that projection; otherwise a
    rejected/deleted certificate can continue to satisfy compliance checks.
    """
    detached_ids = set(detached_certification_ids)
    if not detached_ids:
        return

    # Recompute even when the detached certificates had no expiry. A stale
    # root projection can otherwise survive after the last expiry-less
    # verified medical certificate is rejected or deleted.

    crew = (
        await session.execute(select(CrewMember).where(CrewMember.id == crew_id).with_for_update())
    ).scalar_one_or_none()
    if crew is None or not is_contractor_profile(crew):
        return

    remaining = await session.execute(
        select(Certification).where(
            Certification.crew_member_id == crew_id,
            Certification.id.not_in(detached_ids),
        )
    )
    medical_dates = [
        certification.expiry_date
        for certification in remaining.scalars()
        if certification.expiry_date
        and is_medical_cert_type(certification.cert_type)
        and counts_as_medical_evidence(certification)
    ]
    replacement_expiry = max(medical_dates) if medical_dates else None
    crew.medical_expiry = replacement_expiry
    if replacement_expiry is None:
        crew.medical_status = None
    else:
        crew.medical_status = "fit" if replacement_expiry >= date.today() else "expired"
