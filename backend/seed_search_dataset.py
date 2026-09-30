"""Enrich every local crew record with deterministic AI-search test data.

This is deliberately idempotent: it adds missing, clearly marked work-history
records and qualifications without deleting or replacing imported data.

Usage:
    cd backend && .venv/bin/python seed_search_dataset.py
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import date
from pathlib import Path

DATABASE_PATH = Path(__file__).with_name("hydenlyne.db")
SEED_NAMESPACE = uuid.UUID("2b5c177e-f230-497f-b1f3-fd9e4d78df6f")

PROFILES = [
    {
        "tags": ["Marine Mammal Observer", "PAMGUARD", "Bioacoustics", "Offshore Wind"],
        "certifications": ["BOSIET", "JNCC MMO", "PAMGUARD Advanced", "OGUK Medical"],
        "project_type": "offshore wind environmental monitoring",
        "project_name": "Dogger Bank acoustic mitigation campaign",
        "location": "Aberdeen, UK",
        "country": "UK",
        "role": "Marine Mammal Observer",
        "responsibilities": "Offshore marine mammal monitoring, PAM deployment and JNCC mitigation.",
    },
    {
        "tags": ["Hydrography", "Multibeam", "QINSy", "Offshore Survey"],
        "certifications": [
            "BOSIET",
            "IHO Cat A Hydrographer",
            "Multibeam Bathymetry",
            "QPS QINSy",
            "OGUK Medical",
        ],
        "project_type": "offshore hydrographic survey",
        "project_name": "North Sea cable route survey",
        "location": "Aberdeen, UK",
        "country": "UK",
        "role": "Senior Hydrographic Surveyor",
        "responsibilities": "Offshore multibeam acquisition, QINSy positioning and hydrographic data processing.",
    },
    {
        "tags": ["Geophysics", "Seismic QC", "OBN", "Marine Survey"],
        "certifications": [
            "BOSIET",
            "IOGP Geophysical Rep",
            "Seismic Data Processing",
            "OGUK Medical",
        ],
        "project_type": "marine seismic survey",
        "project_name": "Northern North Sea OBN seismic acquisition",
        "location": "Stavanger, NO",
        "country": "Norway",
        "role": "Geophysical Representative",
        "responsibilities": "Marine seismic acquisition QC, OBN deployment oversight and client reporting.",
    },
    {
        "tags": ["Geotechnical", "CPT", "Vibrocoring", "Foundation Engineering"],
        "certifications": ["BOSIET", "IMCA Geotech", "CPT Testing", "Vibrocoring", "OGUK Medical"],
        "project_type": "offshore geotechnical investigation",
        "project_name": "Offshore wind foundation geotechnical campaign",
        "location": "Rotterdam, NL",
        "country": "Netherlands",
        "role": "Geotechnical Engineer",
        "responsibilities": "Offshore CPT testing, vibrocoring and foundation engineering interpretation.",
    },
    {
        "tags": ["HSE", "Safety Case", "Offshore Construction", "NEBOSH"],
        "certifications": [
            "BOSIET",
            "NEBOSH Diploma",
            "HSE Advisory",
            "Safety Case Compliance",
            "OGUK Medical",
        ],
        "project_type": "offshore construction support",
        "project_name": "North Sea offshore construction campaign",
        "location": "Aberdeen, UK",
        "country": "UK",
        "role": "Offshore HSE Advisor",
        "responsibilities": "Offshore construction HSE leadership, safety case assurance and permit-to-work audits.",
    },
    {
        "tags": ["UXO", "Magnetometer", "ROV", "Cable Route Survey"],
        "certifications": [
            "BOSIET",
            "UXO QC",
            "Magnetometer",
            "ROV Video Verification",
            "OGUK Medical",
        ],
        "project_type": "offshore UXO cable route survey",
        "project_name": "Baltic export cable UXO clearance survey",
        "location": "Hamburg, DE",
        "country": "Germany",
        "role": "UXO QC Specialist",
        "responsibilities": "Offshore UXO survey QC, magnetometer interpretation and ROV target verification.",
    },
]


def seeded_id(crew_id: str, value: str) -> str:
    return str(uuid.uuid5(SEED_NAMESPACE, f"{crew_id}:{value}"))


def merge_tags(current: str | None, additions: list[str]) -> str:
    try:
        tags = json.loads(current or "[]")
    except json.JSONDecodeError:
        tags = []
    if not isinstance(tags, list):
        tags = []
    return json.dumps(list(dict.fromkeys([*tags, *additions])))


def seed() -> None:
    if not DATABASE_PATH.exists():
        raise FileNotFoundError(f"Database not found: {DATABASE_PATH}")

    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    columns = {column[1] for column in connection.execute("PRAGMA table_info(crew_members)")}
    if "experience_months" not in columns:
        connection.execute("ALTER TABLE crew_members ADD COLUMN experience_months INTEGER")
        connection.execute(
            "CREATE INDEX IF NOT EXISTS ix_crew_members_experience_months ON crew_members(experience_months)"
        )
    workers = connection.execute(
        "SELECT id, tags, medical_status FROM crew_members ORDER BY id"
    ).fetchall()
    today = date.today()
    certification_count = work_history_count = 0

    for index, worker in enumerate(workers):
        profile = PROFILES[index % len(PROFILES)]
        tags = merge_tags(worker["tags"], profile["tags"])
        # Preserve a realistic spread: most, rather than all, workers are
        # medical-ready and BOSIET-qualified. Existing imported records win.
        medical_ready = index % 7 != 0
        bosiet_qualified = index % 5 != 0
        certifications = [
            cert
            for cert in profile["certifications"]
            if (cert != "OGUK Medical" or medical_ready) and (cert != "BOSIET" or bosiet_qualified)
        ]
        medical_expiry = (today.replace(year=today.year + 1)).isoformat()
        if medical_ready:
            medical_status = worker["medical_status"] or (
                "fit_with_restrictions" if index % 17 == 0 else "fit"
            )
            connection.execute(
                """UPDATE crew_members
                   SET tags = ?, profile_completeness_score = COALESCE(profile_completeness_score, 85),
                       medical_status = ?, medical_expiry = COALESCE(medical_expiry, ?),
                       medical_provider = CASE
                         WHEN medical_provider = 'OEUK approved provider' THEN 'Search dataset seed (OEUK)'
                         ELSE COALESCE(medical_provider, 'Search dataset seed (OEUK)')
                       END
                   WHERE id = ?""",
                (tags, medical_status, medical_expiry, worker["id"]),
            )
        else:
            connection.execute(
                """UPDATE crew_members
                   SET tags = ?, profile_completeness_score = COALESCE(profile_completeness_score, 85),
                       medical_status = CASE WHEN medical_provider IN ('OEUK approved provider', 'Search dataset seed (OEUK)') THEN NULL ELSE medical_status END,
                       medical_expiry = CASE WHEN medical_provider IN ('OEUK approved provider', 'Search dataset seed (OEUK)') THEN NULL ELSE medical_expiry END,
                       medical_provider = CASE WHEN medical_provider IN ('OEUK approved provider', 'Search dataset seed (OEUK)') THEN NULL ELSE medical_provider END
                   WHERE id = ?""",
                (tags, worker["id"]),
            )

        for cert_type in profile["certifications"]:
            if cert_type not in certifications:
                connection.execute(
                    """DELETE FROM certifications
                       WHERE crew_member_id = ? AND cert_type = ? AND issuing_body = 'Search dataset seed'""",
                    (worker["id"], cert_type),
                )
                continue
            exists = connection.execute(
                "SELECT 1 FROM certifications WHERE crew_member_id = ? AND cert_type = ?",
                (worker["id"], cert_type),
            ).fetchone()
            if not exists:
                connection.execute(
                    """INSERT INTO certifications
                       (id, crew_member_id, cert_type, issuing_body, issue_date, expiry_date, status, verification_status)
                       VALUES (?, ?, ?, 'Search dataset seed', ?, ?, 'valid', 'verified')""",
                    (
                        seeded_id(worker["id"], cert_type),
                        worker["id"],
                        cert_type,
                        today.replace(year=today.year - 1).isoformat(),
                        medical_expiry,
                    ),
                )
                certification_count += 1

        for assignment in (
            profile,
            {**profile, "project_name": f"[Search seed] {profile['project_name']} follow-up"},
        ):
            history_id = seeded_id(worker["id"], assignment["project_name"])
            exists = connection.execute(
                "SELECT 1 FROM work_history WHERE id = ?", (history_id,)
            ).fetchone()
            if not exists:
                connection.execute(
                    """INSERT INTO work_history
                       (id, crew_member_id, project_name, project_type, location, country, role, responsibilities, start_date, end_date, status)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'completed')""",
                    (
                        history_id,
                        worker["id"],
                        assignment["project_name"],
                        assignment["project_type"],
                        assignment["location"],
                        assignment["country"],
                        assignment["role"],
                        assignment["responsibilities"],
                        "2023-03-01",
                        "2024-10-31",
                    ),
                )
                work_history_count += 1

        # Give each test worker a distinct, repeatable career length. Both
        # seeded projects use the same period, so overlapping contracts are
        # counted once when calculating experience.
        experience_years = 2 + (index % 19)
        experience_start = date(today.year - experience_years, 1, 1).isoformat()
        seeded_history_ids = [
            seeded_id(worker["id"], profile["project_name"]),
            seeded_id(worker["id"], f"[Search seed] {profile['project_name']} follow-up"),
        ]
        connection.executemany(
            "UPDATE work_history SET start_date = ?, end_date = ? WHERE id = ?",
            [
                (experience_start, today.isoformat(), history_id)
                for history_id in seeded_history_ids
            ],
        )

        # The seeded contracts deliberately overlap. Their common period is
        # the worker's experience duration, expressed in audited whole months.
        connection.execute(
            "UPDATE crew_members SET experience_months = ? WHERE id = ?",
            (experience_years * 12, worker["id"]),
        )

    connection.commit()
    print(
        f"Enriched {len(workers)} crew members; added {certification_count} certifications and {work_history_count} work-history records."
    )


if __name__ == "__main__":
    seed()
