"""Run database seeds (idempotent) for local development.

Usage:
    cd backend
    .venv/bin/python -m app.seeds
    # or with a target admin (also persists via bootstrap_admin):
    ADMIN_EMAIL=you@hydenlyne.com ADMIN_PASSWORD='YourPass_123!' .venv/bin/python -m app.seeds

Only runs when APP_ENV != "production" to avoid contaminating real data.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import date

from sqlalchemy import select

from app.database import Base, get_engine, get_session_factory
from app.models import Certification, CrewMember, Document, Project
from app.services.crew import bootstrap_admin

# ---------------------------------------------------------------------------
# Seed data — mirrors the 14 fabricated demo consultants so live mode has
# believable records until real profiles are imported.
# ---------------------------------------------------------------------------
SEED_CREW = [
    {
        "full_name": "Dr. Alistair MacIntyre",
        "email": "alistair.macintyre@hydenlyne-network.com",
        "nationality": "British",
        "phone": "+44 (0) 1224 892014",
        "availability_status": "available",
        "role": "user",
        "tags": ["JNCC MMO Certified", "PAMGUARD", "Bioacoustics", "Offshore Wind Mitigation"],
        "profile_completeness_score": 92.0,
    },
    {
        "full_name": "Sarah Van Der Berg",
        "email": "sarah.vanderberg@hydenlyne-network.com",
        "nationality": "Dutch",
        "phone": "+44 (0) 1202 784300",
        "availability_status": "on_assignment",
        "role": "user",
        "tags": ["OBN Quality Control", "Seismic Data Processing", "Survey Audit"],
        "profile_completeness_score": 88.0,
    },
    {
        "full_name": "Gareth Evans",
        "email": "gareth.evans@hydenlyne-network.com",
        "nationality": "British",
        "phone": "+44 (0) 1493 302210",
        "availability_status": "available",
        "role": "user",
        "tags": ["CPT Testing", "Vibrocoring", "Foundation Engineering"],
        "profile_completeness_score": 76.0,
    },
    {
        "full_name": "Helena Lindqvist",
        "email": "helena.lindqvist@hydenlyne-network.com",
        "nationality": "Norwegian",
        "phone": "+47 5 5511 2204",
        "availability_status": "available",
        "role": "user",
        "tags": ["PAMGUARD", "Hydrophone Arrays", "Harbour Porpoise Detection"],
        "profile_completeness_score": 81.0,
    },
    {
        "full_name": "Klaus Lindemann",
        "email": "klaus.lindemann@hydenlyne-network.com",
        "nationality": "Norwegian",
        "phone": "+47 5 1877 4450",
        "availability_status": "on_assignment",
        "role": "user",
        "tags": ["HSE Advisory", "Safety Case Compliance", "IOGP Standards"],
        "profile_completeness_score": 95.0,
    },
    {
        "full_name": "Sophie Moreau",
        "email": "sophie.moreau@hydenlyne-network.com",
        "nationality": "French",
        "phone": "+44 (0) 191 402 7120",
        "availability_status": "available",
        "role": "user",
        "tags": ["Multibeam Bathymetry", "Side Scan Sonar", "QPS QINSy"],
        "profile_completeness_score": 84.0,
    },
    {
        "full_name": "Jonas Lindholm",
        "email": "jonas.lindholm@hydenlyne-network.com",
        "nationality": "Canadian",
        "phone": "+1 (902) 455-1180",
        "availability_status": "unavailable",
        "role": "user",
        "tags": ["UXO QC", "Magnetometer", "ROV Video Verification"],
        "profile_completeness_score": 90.0,
    },
]
# Certifications seeded per crew member (index-matched to SEED_CREW)
# Real offshore operations require OPITO BOSIET/FOET + CA-EBS and OGUK/OEUK Medical
SEED_CERTS = [
    ["OPITO BOSIET with CA-EBS", "OGUK Medical", "JNCC MMO", "STCW"],
    ["OPITO BOSIET with CA-EBS", "OGUK Medical", "IOGP Geophysical Rep", "OBN Quality Control"],
    ["OPITO BOSIET with CA-EBS", "OGUK Medical", "GWO Wind", "IMCA Geotech"],
    ["OPITO BOSIET with CA-EBS", "OGUK Medical", "PAMGUARD Advanced", "NCS Safety"],
    ["OPITO BOSIET with CA-EBS", "OGUK Medical", "NEBOSH Diploma", "ISO 45001 Lead Auditor"],
    ["OPITO BOSIET with CA-EBS", "OGUK Medical", "IHO Cat A Hydrographer", "IMCA Survey QC"],
    ["OPITO BOSIET with CA-EBS", "OGUK Medical", "EOD Level 3", "IMCA Client Rep"],
]


async def seed_all() -> int:
    """Insert seed crew (idempotent by email). Returns number created."""
    factory = get_session_factory()
    created = 0
    async with factory() as session:
        for i, data in enumerate(SEED_CREW):
            exists = await session.execute(
                select(CrewMember).where(CrewMember.email == data["email"])
            )
            existing_crew = exists.scalar_one_or_none()
            if existing_crew:
                # Update compliance fields if not populated
                if not existing_crew.medical_expiry:
                    existing_crew.medical_status = "fit"
                    existing_crew.medical_expiry = date(2027, 12, 31)
                    existing_crew.medical_provider = "Aberdeen Offshore Medical / OEUK"
                    existing_crew.passport_expiry = date(2030, 6, 30)
                    existing_crew.passport_issuing_country = str(data["nationality"])
                continue
            crew = CrewMember(
                id=str(uuid.uuid4()),
                full_name=data["full_name"],
                email=data["email"],
                nationality=data["nationality"],
                phone=data["phone"],
                availability_status=data["availability_status"],
                role=data.get("role", "user"),
                tags=data.get("tags", []),
                profile_completeness_score=data.get("profile_completeness_score"),
                medical_status="fit",
                medical_expiry=date(2027, 12, 31),
                medical_provider="Aberdeen Offshore Medical / OEUK",
                passport_number=f"GB{10000000 + i}",
                passport_expiry=date(2030, 6, 30),
                passport_issuing_country=data["nationality"],
            )
            session.add(crew)
            await session.flush()  # assign id

            # One doc + certs per crew, realistic referencing
            certs = SEED_CERTS[i % len(SEED_CERTS)]
            for cert_type in certs:
                session.add(
                    Certification(
                        id=str(uuid.uuid4()),
                        crew_member_id=crew.id,
                        cert_type=cert_type,
                        issuing_body="OPITO / OEUK / IMCA",
                        issue_date=date(2024, 1, 15),
                        expiry_date=date(2027, 10, 15),
                        status="valid",
                        verification_status="verified",
                    )
                )
            session.add(
                Document(
                    id=str(uuid.uuid4()),
                    crew_member_id=crew.id,
                    file_name=f"{crew.full_name.replace(' ', '_')}_CV.pdf",
                    file_type="pdf",
                    file_size=120000,
                    storage_type="local",
                    storage_path=f"/app/data/documents/{crew.id}/seed_cv.pdf",
                    classification="cv",
                    extraction_status="extracted",
                    uploaded_by="seed",
                )
            )
            created += 1

        await session.commit()

    # Idempotent container records (no email key) — guard against dupes with a marker
    async with factory() as session:
        existing = await session.execute(select(Project).limit(1))
        if existing.scalar_one_or_none() is None:
            session.add(
                Project(
                    id=str(uuid.uuid4()),
                    client_name="Equinor",
                    project_name="Johan Sverdrup 4D OBN Survey",
                    project_type="marine_seismic",
                    location="North Sea",
                    country="Norway",
                    status="active",
                    requirements={"certs": ["BOSIET", "OGUK Medical"]},
                )
            )
            session.add(
                Project(
                    id=str(uuid.uuid4()),
                    client_name="Ørsted",
                    project_name="Dogger Bank Acoustic Mitigation",
                    project_type="offshore_wind",
                    location="North Sea",
                    country="UK",
                    status="planning",
                    requirements={"certs": ["MMO", "PAMGUARD"]},
                )
            )
            await session.commit()

    return created


async def seed_user(
    email: str, password: str, full_name: str = "Ops User", role: str = "user"
) -> CrewMember:
    """Create a non-admin login user (idempotent by email)."""
    from app.auth.session import hash_password

    factory = get_session_factory()
    async with factory() as session:
        exists = await session.execute(select(CrewMember).where(CrewMember.email == email))
        user = exists.scalar_one_or_none()
        if not user:
            user = CrewMember(
                id=str(uuid.uuid4()),
                full_name=full_name,
                email=email,
                role=role,
                password_hash=hash_password(password),
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
        return user


logger = logging.getLogger(__name__)


async def main() -> None:
    from app.config import get_settings

    settings = get_settings()
    if settings.APP_ENV == "production":
        logger.warning("Refusing to seed in production (APP_ENV=production).")
        return

    # Ensure tables exist for the dev sqlite path (create_all), same as init_db
    try:
        engine = get_engine()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    except Exception as e:  # pragma: no cover
        logger.warning("Table init skipped: %s", type(e).__name__)

    n = await seed_all()
    logger.info("Seeded %d crew members (idempotent).", n)

    admin = await bootstrap_admin()
    ops = await seed_user("ops@hydenlyne.com", "OpsPass_123!x", "Ops User", "user")
    logger.info("Admin bootstrap complete: %s", "configured" if admin else "not configured")
    logger.info("Ops user ready (role=%s)", ops.role)


if __name__ == "__main__":
    asyncio.run(main())
