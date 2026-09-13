"""Single source of truth for certification-name normalization.

This is the merged union of what used to be two independently maintained
dictionaries: ``cv_processing.py::CV_CERT_MAPPINGS`` (used when creating
Certification rows from extracted CV data) and
``crew_query.py::CERT_NAME_MAP``/``CERTIFICATION_FAMILIES`` (used when
parsing certification names out of a natural-language search query). They
had already diverged — each held alias keys the other lacked — with no
mechanism to keep them in sync. Both call sites now import from here.
"""

from __future__ import annotations

# alias/typo/shorthand (lowercase) -> canonical certificate name.
CERT_ALIASES: dict[str, str] = {
    "mmo": "JNCC MMO",
    "jncc": "JNCC MMO",
    "environmental": "JNCC MMO",
    "pam": "PAMGUARD Advanced",
    "pamguard": "PAMGUARD Advanced",
    "qps": "QPS QINSy",
    "qinsy": "QPS QINSy",
    "multibeam": "Multibeam Bathymetry",
    "side scan": "Side Scan Sonar",
    "magnetometer": "Magnetometer",
    "rov": "ROV Video Verification",
    "cpt": "CPT Testing",
    "seismic": "Seismic Data Processing",
    "hse": "HSE Advisory",
    "bosiet": "BOSIET",
    "stcw": "STCW",
    "oguk": "OGUK Medical",
    "oguk medical": "OGUK Medical",
    "oeuk": "OGUK Medical",
    "oeuk medical": "OGUK Medical",
    "offshore medical": "OGUK Medical",
    "offshore_medical": "OGUK Medical",
    "eng1": "OGUK Medical",
    "eng1 medical": "OGUK Medical",
    "nebosh": "NEBOSH Diploma",
    "nebosch": "NEBOSH Diploma",
    "iho": "IHO Cat A Hydrographer",
    "iho cat a": "IHO Cat A Hydrographer",
    "hydrography": "IHO Cat A Hydrographer",
    "hydrographer": "IHO Cat A Hydrographer",
    "iogp": "IOGP Geophysical Rep",
    "igp": "IOGP Geophysical Rep",
    "geophysical": "IOGP Geophysical Rep",
    "geophysicist": "IOGP Geophysical Rep",
    "geophysical rep": "IOGP Geophysical Rep",
    "imca": "IMCA Survey QC",
    "imca survey": "IMCA Survey QC",
    "survey qc": "IMCA Survey QC",
    "imca geotech": "IMCA Geotech",
    "geotech": "IMCA Geotech",
    "imca client rep": "IMCA Client Rep",
    "client rep": "IMCA Client Rep",
    "gwo": "GWO Wind",
    "gwo wind": "GWO Wind",
    "eod": "EOD Level 3",
    "uxo": "UXO QC",
    "ncs": "NCS Safety",
    "ncs safety": "NCS Safety",
    "iso 45001": "ISO 45001 Lead Auditor",
    "vibrocoring": "Vibrocoring",
    "vibro": "Vibrocoring",
    "foundation": "Foundation Engineering",
    "hydrophone": "Hydrophone Arrays",
    "harbour porpoise": "Harbour Porpoise Detection",
    "safety case": "Safety Case Compliance",
    "offshore medic": "Offshore Medic",
    "huet": "HUET",
    "ca-ebs": "CA-EBS",
    "foet": "FOET",
    "opito hda": "OPITO HDA",
}

# Broad credential families are common in a recruiter's wording. They must
# search their concrete certificate types rather than an imaginary exact type
# such as "IMCA".
CERT_FAMILIES: dict[str, str] = {
    "imca": "IMCA",
    "opito": "OPITO",
    "iogp": "IOGP",
}


def is_medical_cert_type(name: str | None) -> bool:
    """Return whether a certificate name represents offshore medical evidence."""
    if not isinstance(name, str):
        return False
    normalized = name.casefold()
    return any(keyword in normalized for keyword in ("medical", "oguk", "oeuk", "eng1"))


def normalize_cert_name(name: str) -> str:
    """Normalize a raw/extracted certification name to canonical form."""
    lower = name.lower().strip()
    if lower in CERT_ALIASES:
        return CERT_ALIASES[lower]
    for key, value in CERT_ALIASES.items():
        if key in lower or lower in key:
            return value
    return name.upper()


def cert_family_for(text: str) -> str | None:
    """Return the credential family (e.g. "IMCA") a keyword belongs to, if any."""
    lower = text.lower()
    for keyword, family in CERT_FAMILIES.items():
        if keyword in lower:
            return family
    return None
