"""Enrich crew compliance data for local development.

Populates valid OPITO BOSIET/FOET certifications, OGUK/OEUK Medicals,
and crew_members.medical_expiry so that qualified candidates show
as Compliant in the Agent Mobilization pre-flight matrix.
"""

import asyncio
import uuid
from datetime import date

from sqlalchemy import select

from app.database import get_session_factory
from app.models import Certification, CrewMember


async def enrich_crew():
    factory = get_session_factory()
    async with factory() as session:
        stmt = select(CrewMember)
        res = await session.execute(stmt)
        crew_members = list(res.scalars().all())

        print(f"Loaded {len(crew_members)} crew members")

        updated_crew = 0
        added_certs = 0
        updated_certs = 0

        for crew in crew_members:
            # Query existing certs
            c_stmt = select(Certification).where(Certification.crew_member_id == crew.id)
            c_res = await session.execute(c_stmt)
            certs = list(c_res.scalars().all())

            # Check for existing survival & medical certs
            survival_cert = next(
                (
                    c
                    for c in certs
                    if any(
                        k in (c.cert_type or "").lower()
                        for k in ("bosiet", "foet", "survival", "ca-ebs")
                    )
                ),
                None,
            )
            medical_cert = next(
                (
                    c
                    for c in certs
                    if any(
                        k in (c.cert_type or "").lower()
                        for k in ("medical", "oguk", "oeuk", "eng1")
                    )
                ),
                None,
            )

            # For available or on_assignment specialists: ensure full compliance
            if crew.availability_status in ("available", "on_assignment"):
                # 1. Update crew medical fields
                if not crew.medical_expiry or crew.medical_expiry < date(2027, 1, 1):
                    crew.medical_status = "fit_for_offshore"
                    crew.medical_expiry = date(2027, 12, 15)
                    crew.medical_provider = "OEUK Approved Clinic"
                    updated_crew += 1

                if not crew.passport_expiry or crew.passport_expiry < date(2027, 1, 1):
                    crew.passport_expiry = date(2030, 6, 30)
                    if not crew.passport_issuing_country:
                        crew.passport_issuing_country = crew.nationality or "United Kingdom"
                    if not crew.passport_number:
                        crew.passport_number = f"P{str(uuid.uuid4())[:8].upper()}"

                # 2. Update or create Survival cert
                if survival_cert:
                    survival_cert.status = "valid"
                    survival_cert.verification_status = "verified"
                    if not survival_cert.expiry_date or survival_cert.expiry_date < date(
                        2027, 1, 1
                    ):
                        survival_cert.expiry_date = date(2027, 10, 31)
                    survival_cert.issuing_body = "OPITO"
                    updated_certs += 1
                else:
                    new_survival = Certification(
                        id=str(uuid.uuid4()),
                        crew_member_id=crew.id,
                        cert_type="OPITO BOSIET with CA-EBS",
                        issuing_body="OPITO",
                        issue_date=date(2023, 11, 1),
                        expiry_date=date(2027, 10, 31),
                        status="valid",
                        verification_status="verified",
                        cert_number=f"OPT-{str(uuid.uuid4())[:8].upper()}",
                    )
                    session.add(new_survival)
                    added_certs += 1

                # 3. Update or create Medical cert
                if medical_cert:
                    medical_cert.status = "valid"
                    medical_cert.verification_status = "verified"
                    if not medical_cert.expiry_date or medical_cert.expiry_date < date(2027, 1, 1):
                        medical_cert.expiry_date = date(2027, 12, 15)
                    medical_cert.issuing_body = "OEUK"
                    updated_certs += 1
                else:
                    new_med = Certification(
                        id=str(uuid.uuid4()),
                        crew_member_id=crew.id,
                        cert_type="OGUK Medical",
                        issuing_body="OEUK",
                        issue_date=date(2025, 12, 1),
                        expiry_date=date(2027, 12, 15),
                        status="valid",
                        verification_status="verified",
                        cert_number=f"OEUK-{str(uuid.uuid4())[:8].upper()}",
                    )
                    session.add(new_med)
                    added_certs += 1

                # Also verify other discipline certs if pending
                for c in certs:
                    if c.status == "pending_verification" or c.verification_status == "unverified":
                        c.status = "valid"
                        c.verification_status = "verified"
                        if not c.expiry_date:
                            c.expiry_date = date(2028, 4, 30)
                        updated_certs += 1

            elif crew.availability_status == "unavailable":
                # For unavailable, set expired medical for realism
                if not crew.medical_expiry:
                    crew.medical_status = "expired"
                    crew.medical_expiry = date(2025, 8, 10)
                    updated_crew += 1

        await session.commit()
        print(
            f"Enrichment complete: {updated_crew} crew updated, {added_certs} certs added, {updated_certs} certs updated."
        )


if __name__ == "__main__":
    asyncio.run(enrich_crew())
