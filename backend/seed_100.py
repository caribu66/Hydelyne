"""Generate 100 diverse crew members for AI search testing."""
from __future__ import annotations

import asyncio
import random
import uuid
from datetime import date, timedelta

from sqlalchemy import select

from app.database import Base, get_engine, get_session_factory
from app.models import Certification, CrewMember

FIRST_NAMES = [
    "James", "Mary", "Robert", "Patricia", "John", "Jennifer", "Michael", "Linda",
    "David", "Elizabeth", "William", "Barbara", "Richard", "Susan", "Joseph", "Jessica",
    "Thomas", "Sarah", "Charles", "Karen", "Christopher", "Lisa", "Daniel", "Nancy",
    "Matthew", "Betty", "Anthony", "Margaret", "Mark", "Sandra", "Donald", "Ashley",
    "Steven", "Kimberly", "Paul", "Emily", "Andrew", "Donna", "Joshua", "Michelle",
    "Kenneth", "Carol", "Kevin", "Amanda", "Brian", "Dorothy", "George", "Melissa",
    "Timothy", "Deborah", "Ronald", "Stephanie", "Edward", "Rebecca", "Jason", "Sharon",
    "Jeffrey", "Laura", "Ryan", "Cynthia", "Jacob", "Kathleen", "Gary", "Amy",
    "Nicholas", "Angela", "Eric", "Shirley", "Jonathan", "Anna", "Stephen", "Brenda",
    "Larry", "Pamela", "Justin", "Emma", "Scott", "Nicole", "Brandon", "Helen",
    "Benjamin", "Samantha", "Samuel", "Katherine", "Raymond", "Christine", "Gregory", "Debra",
    "Frank", "Rachel", "Alexander", "Carolyn", "Patrick", "Janet", "Jack", "Catherine",
]

LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis",
    "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson", "Thomas",
    "Taylor", "Moore", "Jackson", "Martin", "Lee", "Perez", "Thompson", "White",
    "Harris", "Sanchez", "Clark", "Ramirez", "Lewis", "Robinson", "Walker", "Young",
    "Allen", "King", "Wright", "Scott", "Torres", "Nguyen", "Hill", "Flores",
    "Green", "Adams", "Nelson", "Baker", "Hall", "Rivera", "Campbell", "Mitchell",
    "Carter", "Roberts", "Chen", "Mueller", "Schmidt", "Schneider", "Fischer", "Weber",
    "Meyer", "Wagner", "Becker", "Schulz", "Hoffmann", "Koch", "Bauer", "Richter",
    "Klein", "Wolf", "Schroder", "Neumann", "Schwarz", "Zimmermann", "Braun", "Kruger",
    "Larsen", "Pedersen", "Andersen", "Nielsen", "Christensen", "Jensen", "Madsen",
    "Olsen", "Holm", "Rasmussen", "Poulsen", "Johansen", "Moller", "Knutson", "Eriksson",
    "MacIntyre", "Van Der Berg", "Lindqvist", "Lindemann", "Moreau", "Lindholm",
]

NATIONALITIES = [
    "British", "Dutch", "Norwegian", "French", "Canadian", "German", "Danish",
    "Swedish", "Australian", "American", "Irish", "Belgian", "Spanish", "Italian",
    "New Zealander", "Singaporean", "Maltese", "Greek", "Finnic", "Icelandic",
]

AVAILABILITY_STATUSES = ["available", "on_assignment", "unavailable"]

CERTIFICATIONS_POOL = [
    "BOSIET", "STCW", "OGUK Medical", "JNCC MMO", "PAMGUARD Advanced",
    "NCS Safety", "NEBOSH Diploma", "ISO 45001 Lead Auditor", "GWO Wind",
    "IMCA Geotech", "IHO Cat A Hydrographer", "IMCA Survey QC", "EOD Level 3",
    "IMCA Client Rep", "IOGP Geophysical Rep", "OBN Quality Control",
    "Multibeam Bathymetry", "Side Scan Sonar", "QPS QINSy", "CPT Testing",
    "Vibrocoring", "Foundation Engineering", "Hydrophone Arrays", "Harbour Porpoise Detection",
    "HSE Advisory", "Safety Case Compliance", "IOGP Standards", "UXO QC",
    "Magnetometer", "ROV Video Verification", "Seismic Data Processing", "Survey Audit",
    "Offshore Medic", "HUET", "CA-EBS", "FOET", "OPITO HDA",
]

LOCATIONS = [
    "Aberdeen, UK", "London, UK", "Rotterdam, NL", "Amsterdam, NL",
    "Oslo, NO", "Bergen, NO", "Stavanger, NO", "Paris, FR", "Marseille, FR",
    "Houston, US", "New York, US", "Halifax, CA", "Vancouver, CA",
    "Hamburg, DE", "Copenhagen, DK", "Stockholm, SE", "Perth, AU",
    "Singapore, SG", "Valletta, MT", "Athens, GR", "Reykjavik, IS",
    "Dublin, IE", "Brussels, BE", "Madrid, ES", "Rome, IT",
]


def random_date(start_year: int = 2024, end_year: int = 2027) -> date:
    start = date(start_year, 1, 1)
    end = date(end_year, 12, 31)
    days = (end - start).days
    return start + timedelta(days=random.randint(0, days))


async def generate_crew(count: int = 100) -> int:
    factory = get_session_factory()
    created = 0

    async with factory() as session:
        # Get existing emails to avoid duplicates
        result = await session.execute(select(CrewMember.email))
        existing_emails = {row[0] for row in result.all() if row[0]}

        for i in range(count):
            first = random.choice(FIRST_NAMES)
            last = random.choice(LAST_NAMES)
            full_name = f"{first} {last}"
            email = f"{first.lower()}.{last.lower()}-{i}@hydenlyne-network.com"

            if email in existing_emails:
                continue

            availability = random.choice(AVAILABILITY_STATUSES)

            crew = CrewMember(
                id=str(uuid.uuid4()),
                full_name=full_name,
                email=email,
                nationality=random.choice(NATIONALITIES),
                phone=f"+{random.randint(1,99)} {random.randint(100,999)} {random.randint(1000999,9999999)}",
                availability_status=availability,
                role="user",
                tags=random.sample(CERTIFICATIONS_POOL, k=random.randint(2, 5)),
                profile_completeness_score=round(random.uniform(60, 99), 1),
            )
            session.add(crew)
            await session.flush()

            # Add 2-5 random certifications
            num_certs = random.randint(2, 5)
            crew_certs = random.sample(CERTIFICATIONS_POOL, k=num_certs)
            for cert_type in crew_certs:
                session.add(
                    Certification(
                        id=str(uuid.uuid4()),
                        crew_member_id=crew.id,
                        cert_type=cert_type,
                        issuing_body=random.choice(["OPITO", "IMCA", "IHO", "NEBOSH", "OGUK"]),
                        expiry_date=random_date(2025, 2028) if random.random() > 0.3 else None,
                        status=random.choice(["valid", "expiring_soon", "expired", "pending_verification"]),
                        verification_status=random.choice(["verified", "unverified", "pending"]),
                    )
                )

            existing_emails.add(email)
            created += 1

        await session.commit()

    return created


async def main() -> None:
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    n = await generate_crew(100)
    print(f"Created {n} new crew members")


if __name__ == "__main__":
    asyncio.run(main())
