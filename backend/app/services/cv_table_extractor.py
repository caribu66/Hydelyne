"""Deterministic CV table extractor backed by pdfplumber.

The Helena Lindqvist CV (and similar real-world consultant CVs) presents
structured sections as PDF tables with column headers like
``TYPE | PLACE | DATE COMPLETED | EXPIRY DATE``.  When the document is
flattened to plain text with ``page.extract_text()``, those columns are
scrambled because the TYPE column is wider than the others and wraps onto
multiple visual lines.

This service walks every page, identifies the well-known sections by their
header cell, and reconstructs them as structured records.  It does not
replace the LLM extractor — it complements it by providing reliable,
deterministic rows for the parts of the CV that are tables.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Iterable, Optional

logger = logging.getLogger(__name__)


SECTION_HEADERS = {
    "training": re.compile(
        r"\bTRAINING(?:/QUALIFICATIONS)?\b|\bCERTIFICATIONS?\b|\bCERTIFICATES?\b", re.I
    ),
    "geography": re.compile(r"\bGEOGRAPHICAL\s+EXPERIENCE\b|\bGEOGRAPHY\b", re.I),
    "systems": re.compile(r"\bSYSTEMS\s+EXPERIENCE\b", re.I),
    "projects": re.compile(r"\bRECENT\s+PROJECTS?\b|\bPROJECT\s+HISTORY\b", re.I),
    "personal": re.compile(r"\bPERSONAL\s+INFORMATION\b|\bPERSONAL\s+DETAILS\b", re.I),
    "expertise": re.compile(r"^\s*EXPERTISE\s*$", re.I),
    "summary": re.compile(r"^\s*PROFESSIONAL\s+SUMMARY\s*$", re.I),
}

# The free-text "Skills & Competencies" sub-list sits inside the
# PROFESSIONAL SUMMARY section, introduced by this exact label in the
# template. Splitting on it is purely mechanical (find the line, take
# everything after it) — no interpretation of what any bullet means.
_SKILLS_SUBHEADER = re.compile(r"^\s*Skills\s*&\s*Competencies\s*:?\s*$", re.I)

# A plausible CV title line: 2-6 space-separated word-like tokens, no digits.
_NAME_LINE = re.compile(r"^[A-Za-z][A-Za-z.'\-]*(?:\s+[A-Za-z][A-Za-z.'\-]*){1,5}$")


@dataclass
class TrainingRecord:
    name: str
    place: str | None = None
    completed: str | None = None
    expiry: str | None = None

    def as_extraction_string(self) -> str:
        parts = [self.name]
        if self.place:
            parts.append(self.place)
        if self.completed:
            parts.append(f"Completed {self.completed}")
        if self.expiry:
            parts.append(f"Expires {self.expiry}")
        return " — ".join(parts)

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "place": self.place,
            "completed_date": self.completed,
            "expiry_date": self.expiry,
        }


@dataclass
class ProjectRecord:
    year: str | None = None
    client: str | None = None
    country: str | None = None
    survey_type: str | None = None
    vessel: str | None = None
    position: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "year": self.year,
            "client": self.client,
            "country": self.country,
            "survey_type": self.survey_type,
            "vessel": self.vessel,
            "position": self.position,
        }


@dataclass
class SystemsRecord:
    category: str
    items: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {"category": self.category, "items": self.items}


@dataclass
class GeographyRecord:
    region: str
    locations: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {"region": self.region, "locations": self.locations}


@dataclass
class PersonalRecord:
    fields: dict[str, str] = field(default_factory=dict)

    def as_dict(self) -> dict[str, str]:
        return dict(self.fields)


@dataclass
class CVTableExtraction:
    personal: Optional[PersonalRecord] = None
    expertise: list[str] = field(default_factory=list)
    geography: list[GeographyRecord] = field(default_factory=list)
    systems: list[SystemsRecord] = field(default_factory=list)
    training: list[TrainingRecord] = field(default_factory=list)
    projects: list[ProjectRecord] = field(default_factory=list)
    full_name: Optional[str] = None
    professional_summary: Optional[str] = None
    skills: list[str] = field(default_factory=list)

    def as_extraction_payload(self) -> dict[str, Any]:
        """Return a dict shaped like the LLM extraction output."""
        payload: dict[str, Any] = {}
        if self.full_name:
            payload["full_name"] = self.full_name
        if self.professional_summary:
            payload["professional_summary"] = self.professional_summary
        if self.skills:
            payload["skills"] = self.skills
        if self.personal and self.personal.fields:
            payload["personal_information"] = self.personal.fields
        if self.expertise:
            payload["expertise"] = self.expertise
        if self.geography:
            payload["geographical_experience"] = [
                item for record in self.geography for item in record.locations
            ]
        if self.systems:
            payload["systems"] = [item for record in self.systems for item in record.items]
        if self.training:
            payload["training_qualifications"] = [
                record.as_extraction_string() for record in self.training
            ]
            payload["training_qualifications_structured"] = [
                record.as_dict() for record in self.training
            ]
            cert_names: list[str] = []
            for record in self.training:
                short = _short_cert_name(record.name)
                if short:
                    cert_names.append(short)
            if cert_names:
                payload["certifications"] = cert_names
        if self.projects:
            work_history: list[dict[str, Any]] = []
            for project in self.projects:
                start_date = _year_to_iso(project.year)
                work_history.append(
                    {
                        "client": project.client,
                        "project": None,
                        "project_type": project.survey_type,
                        # The template has no true "location" column, only
                        # CONTRACTOR/VESSEL — leave location unset rather than
                        # mislabeling vessel data as a location.
                        "location": None,
                        "country": project.country,
                        "role": project.position,
                        "start_date": start_date,
                        "end_date": None,
                        "responsibilities": None,
                    }
                )
            payload["work_history"] = work_history
        return payload


def extract_cv_tables(pdf_path: str) -> CVTableExtraction:
    """Walk every page of ``pdf_path`` and recover the structured sections."""
    try:
        import pdfplumber
    except ImportError as exc:
        raise RuntimeError("pdfplumber is required for CV table extraction") from exc

    extraction = CVTableExtraction()
    last_section: str | None = None
    last_column_shape: tuple[int, ...] | None = None
    pending_project: ProjectRecord | None = None

    with pdfplumber.open(pdf_path) as pdf:
        page_tables = [(page, page.extract_tables() or []) for page in pdf.pages]
        page_texts = [page.extract_text() or "" for page in pdf.pages]

    if page_texts:
        extraction.full_name = _extract_full_name(page_texts[0])
        extraction.professional_summary, extraction.skills = _extract_free_text_sections(
            "\n".join(page_texts)
        )

    for page, tables in page_tables:
        for raw_table in tables:
            if not raw_table:
                continue
            shape = _column_shape(raw_table)
            classified = _classify_table(raw_table) or (
                last_section if shape == last_column_shape else None
            )
            # Continuation tables on the next page may have a different
            # column count (e.g. 8-col header → 6-col data).  Allow a
            # looser match for project continuations: same column count
            # OR same number of non-empty cells in at least one row.
            if classified is None and last_section == "projects":
                classified = _looks_like_project_continuation(raw_table)
            if classified is None:
                continue
            try:
                if classified == "personal":
                    extraction.personal = _extract_personal(raw_table)
                elif classified == "expertise":
                    extraction.expertise.extend(_extract_expertise(raw_table))
                elif classified == "geography":
                    extraction.geography.extend(_extract_geography(raw_table))
                elif classified == "systems":
                    extraction.systems.extend(_extract_systems(raw_table))
                elif classified == "training":
                    extraction.training.extend(
                        _extract_training(raw_table, header_row_index_hint=0)
                    )
                elif classified == "projects":
                    finalised, pending_project = _extract_projects(raw_table, pending_project)
                    extraction.projects.extend(finalised)
            except Exception as exc:
                logger.warning(
                    "Failed to parse %s table on page %s: %s",
                    classified,
                    getattr(page, "page_number", "?"),
                    exc,
                )
            last_section = classified
            last_column_shape = shape

    if pending_project is not None:
        extraction.projects.append(pending_project)

    return extraction


def _column_shape(table: list[list[str | None]]) -> tuple[int, ...]:
    return tuple(sum(1 for cell in row if cell and cell.strip()) for row in table)


def _classify_table(table: list[list[str | None]]) -> str | None:
    for row in table:
        for cell in row:
            if not cell:
                continue
            text = cell.strip()
            if not text:
                continue
            for name, pattern in SECTION_HEADERS.items():
                if pattern.search(text):
                    return name
            if not _looks_like_header(text):
                return None
    return None


def _looks_like_header(cell: str) -> bool:
    if len(cell) > 60:
        return False
    lowered = cell.lower()
    if lowered.startswith(("experienced", "skilled", "qualified", "able", "strong", "proficient")):
        return False
    return True


def _extract_full_name(first_page_text: str) -> str | None:
    """The template's name is always the first non-empty line, before any
    section header. Validate it looks name-like rather than trusting it
    blindly — if it doesn't, leave it unset so the document goes to review
    instead of storing a wrong guess."""
    for line in first_page_text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if any(pattern.search(stripped) for pattern in SECTION_HEADERS.values()):
            return None
        if len(stripped) <= 60 and _NAME_LINE.match(stripped):
            return _normalise_whitespace(stripped.title() if stripped.isupper() else stripped)
        return None
    return None


def _extract_free_text_sections(full_text: str) -> tuple[str | None, list[str]]:
    """Capture the PROFESSIONAL SUMMARY section verbatim: the narrative
    paragraph as-is, and the "Skills & Competencies" bullets as a plain
    list. Mechanical text splitting only — no interpretation of content."""
    lines = full_text.splitlines()
    start = None
    for index, line in enumerate(lines):
        if SECTION_HEADERS["summary"].search(line.strip()):
            start = index + 1
            break
    if start is None:
        return None, []

    end = len(lines)
    for index in range(start, len(lines)):
        stripped = lines[index].strip()
        if not stripped:
            continue
        if any(
            name != "summary" and pattern.search(stripped)
            for name, pattern in SECTION_HEADERS.items()
        ):
            end = index
            break

    section_lines = lines[start:end]

    skills_start = None
    for index, line in enumerate(section_lines):
        if _SKILLS_SUBHEADER.match(line.strip()):
            skills_start = index
            break

    if skills_start is None:
        summary_lines = section_lines
        skills_lines: list[str] = []
    else:
        summary_lines = section_lines[:skills_start]
        skills_lines = section_lines[skills_start + 1 :]

    summary_text = "\n".join(line.strip() for line in summary_lines if line.strip()).strip()
    # A bullet that wraps across two PDF text lines has no bullet glyph on
    # its continuation line — merge it into the previous entry instead of
    # treating it as a new one.
    skills: list[str] = []
    for line in skills_lines:
        stripped = line.strip()
        if not stripped:
            continue
        if _BULLET_PREFIX.match(stripped) or not skills:
            skills.append(_strip_bullet(stripped))
        else:
            skills[-1] = f"{skills[-1]} {stripped}"
    return (summary_text or None), skills


# This template's bullet glyph decodes to a Private Use Area codepoint
# (U+E000-U+F8FF) from its icon font, not a standard bullet character —
# confirmed against the real fixture (U+F0A7). Strip any PUA lead-in char
# alongside ordinary bullet characters.
_BULLET_PREFIX = re.compile(r"^[\u2022\u00b7\-*\ue000-\uf8ff]+\s*")


def _strip_bullet(line: str) -> str:
    return _BULLET_PREFIX.sub("", line).strip()


def _looks_like_project_continuation(table: list[list[str | None]]) -> str | None:
    """Detect a headerless project continuation table by content heuristics."""
    year_re = re.compile(r"^\s*(19|20)\d{2}\b")
    for row in table:
        cells = [c.strip() if c else "" for c in row]
        if cells and year_re.match(cells[0]):
            return "projects"
    return None


def _extract_personal(table: list[list[str | None]]) -> PersonalRecord:
    fields: dict[str, str] = {}
    for row in table:
        cleaned = [cell.strip() for cell in row if cell and cell.strip()]
        if len(cleaned) < 2:
            continue
        key = cleaned[0].upper()
        value = " ".join(cleaned[1:]).strip()
        if not value or value.upper() == key:
            continue
        fields[key] = value
    return PersonalRecord(fields=fields)


def _extract_expertise(table: list[list[str | None]]) -> list[str]:
    items: list[str] = []
    for row in table:
        for cell in row:
            if not cell:
                continue
            text = cell.strip()
            if not text or SECTION_HEADERS["expertise"].match(text):
                continue
            for piece in re.split(r"[\n,;•·\u2022]+", text):
                # The delimiter split above catches standard bullets between
                # items, but this template's own bullet glyph is a Private
                # Use Area character (see _strip_bullet) that can lead an
                # item rather than separate two -- strip it too.
                piece = _strip_bullet(piece.strip())
                if piece and piece.lower() not in (i.lower() for i in items):
                    items.append(piece)
    return items


def _extract_geography(table: list[list[str | None]]) -> list[GeographyRecord]:
    records: list[GeographyRecord] = []
    for row in table:
        cleaned = [cell.strip() for cell in row if cell and cell.strip()]
        if len(cleaned) < 2:
            continue
        region = cleaned[0]
        location_text = " ".join(cleaned[1:])
        locations = [piece.strip() for piece in re.split(r",|;", location_text) if piece.strip()]
        if not locations:
            continue
        records.append(GeographyRecord(region=region, locations=locations))
    return records


def _extract_systems(table: list[list[str | None]]) -> list[SystemsRecord]:
    records: list[SystemsRecord] = []
    for row in table:
        cleaned = [cell.strip() for cell in row if cell and cell.strip()]
        if len(cleaned) < 2:
            continue
        category = cleaned[0]
        items_text = " ".join(cleaned[1:])
        items = [piece.strip() for piece in re.split(r"\n", items_text) if piece.strip()]
        if not items:
            continue
        records.append(SystemsRecord(category=category, items=items))
    return records


def _extract_training(
    table: list[list[str | None]],
    header_row_index_hint: int | None = None,
) -> Iterable[TrainingRecord]:
    rows = [r for r in table if any(cell and cell.strip() for cell in r)]
    if not rows:
        return []

    header_row_index = -1
    search_window = min(3, len(rows))
    start = header_row_index_hint if header_row_index_hint is not None else 0
    for candidate in range(start, min(start + search_window, len(rows))):
        cells_text = " ".join((cell or "") for cell in rows[candidate]).upper()
        if "TYPE" in cells_text or "COURSE" in cells_text or "CERT" in cells_text:
            header_row_index = candidate
            break

    if header_row_index == -1:
        column_map: Optional[dict[str, int]] = {"name": 0, "place": 1, "completed": 2, "expiry": 3}
        data_rows = rows
    else:
        header = [cell.strip() if cell else "" for cell in rows[header_row_index]]
        column_map = _map_training_columns(header)
        if column_map is None:
            return []
        data_rows = rows[header_row_index + 1 :]

    if column_map is None:
        # Unreachable: both branches above either assign a literal map or
        # return early on None — kept as a real check, not assert, since
        # `python -O` strips asserts and this guards a dict-index below.
        raise RuntimeError("_extract_training_table: column_map was not resolved")
    out: list[TrainingRecord] = []
    for row in data_rows:
        cells = [cell.strip() if cell else "" for cell in row]
        if not any(cells):
            continue
        name_idx = column_map["name"]
        name = cells[name_idx] if name_idx < len(cells) else ""
        if not name:
            continue
        place_idx = column_map["place"]
        completed_idx = column_map["completed"]
        expiry_idx = column_map["expiry"]
        out.append(
            TrainingRecord(
                name=_normalise_whitespace(name, join_with_space=True),
                place=_normalise_whitespace(cells[place_idx]) if place_idx < len(cells) else None,
                completed=_normalise_whitespace(cells[completed_idx])
                if completed_idx < len(cells)
                else None,
                expiry=_normalise_whitespace(cells[expiry_idx])
                if expiry_idx < len(cells)
                else None,
            )
        )
    return out


def _map_training_columns(header: list[str]) -> dict[str, int] | None:
    column_map: dict[str, int] = {}
    for index, cell in enumerate(header):
        upper = cell.upper()
        if "TYPE" in upper or "COURSE" in upper or "CERT" in upper:
            column_map.setdefault("name", index)
        elif "PLACE" in upper or "LOCATION" in upper or "VENUE" in upper:
            column_map["place"] = index
        elif "COMPLETE" in upper or "ISSUED" in upper:
            column_map["completed"] = index
        elif "EXPIRY" in upper or "EXPIRES" in upper or "RENEWAL" in upper:
            column_map["expiry"] = index
    if "name" not in column_map:
        return None
    column_map.setdefault("place", 1)
    column_map.setdefault("completed", 2)
    column_map.setdefault("expiry", 3)
    return column_map


def _extract_projects(
    table: list[list[str | None]],
    pending: ProjectRecord | None = None,
) -> tuple[list[ProjectRecord], ProjectRecord | None]:
    """Recover RECENT PROJECTS rows.

    Returns a tuple of (finalised_records, open_record).  The caller hands
    the open record back into the next call when it sees a continuation
    table on the next page so the trailing project can keep growing.
    """
    rows = [r for r in table if any(cell and cell.strip() for cell in r)]
    if not rows:
        return [], pending

    header_row_index = -1
    column_positions: dict[str, int] = {}
    for candidate in range(min(2, len(rows))):
        cells_text = " ".join((cell or "") for cell in rows[candidate]).upper()
        if "YEAR" in cells_text:
            header_row_index = candidate
            column_positions = _map_project_columns(
                [(cell or "").strip() for cell in rows[candidate]]
            )
            break

    data_rows = rows[header_row_index + 1 :] if header_row_index >= 0 else rows
    if not data_rows:
        return [], pending

    # When no header row was found (continuation tables), default to
    # the standard 6-column layout.
    if not column_positions:
        column_positions = {
            "year": 0,
            "client": 1,
            "country": 2,
            "survey_type": 3,
            "vessel": 4,
            "position": 5,
        }

    finalised: list[ProjectRecord] = []
    current = pending
    for row in data_rows:
        cols = [c.strip() if c else "" for c in row]
        # Detect new project row: first non-empty cell looks like a year
        first_cell = cols[0] if cols else ""
        is_new = bool(
            re.match(r"^\s*(19|20)\d{2}\b", first_cell)
            or re.match(r"^\s*\d{4}\s*[-–]\s*\d{4}", first_cell)
        )

        # Auto-detect column layout: if we see a year in col 0 and a known
        # client name in col 1 (skipping a blank col), it's the 8-col layout
        # with an empty spacer column.
        if column_positions and len(cols) > max(column_positions.values()):
            # Check for blank spacer between year and client
            if is_new and len(cols) >= 7 and not cols[1]:
                column_positions = {
                    "year": 0,
                    "client": 2,
                    "country": 3,
                    "survey_type": 4,
                    "vessel": 5,
                    "position": 6,
                }
            elif column_positions.get("year") == 0 and not column_positions.get("client"):
                # No explicit header — infer from position
                column_positions = {
                    "year": 0,
                    "client": 1,
                    "country": 2,
                    "survey_type": 3,
                    "vessel": 4,
                    "position": 5,
                }

        if is_new:
            if current is not None:
                finalised.append(current)
            current = ProjectRecord(year=first_cell or None)
        if current is None:
            continue
        for field_name, idx in column_positions.items():
            if field_name == "year":
                continue
            if idx >= len(cols):
                continue
            value = cols[idx]
            if not value:
                continue
            existing = getattr(current, field_name) or ""
            setattr(
                current,
                field_name,
                (existing + " " + _normalise_whitespace(value, join_with_space=True)).strip()
                if existing
                else _normalise_whitespace(value, join_with_space=True),
            )
    return finalised, current


def _map_project_columns(header: list[str]) -> dict[str, int]:
    column_map: dict[str, int] = {}
    for index, cell in enumerate(header):
        upper = cell.upper()
        if "YEAR" in upper:
            column_map["year"] = index
        elif "CLIENT" in upper:
            column_map["client"] = index
        elif "COUNTRY" in upper:
            column_map["country"] = index
        elif "SURVEY" in upper or "TYPE" in upper:
            column_map["survey_type"] = index
        elif "VESSEL" in upper or "CONTRACTOR" in upper:
            column_map["vessel"] = index
        elif "POSITION" in upper or "ROLE" in upper:
            column_map["position"] = index
    if "year" not in column_map:
        return {}
    column_map.setdefault("client", 1)
    column_map.setdefault("country", 2)
    column_map.setdefault("survey_type", 3)
    column_map.setdefault("vessel", 4)
    column_map.setdefault("position", 5)
    return column_map


def _normalise_whitespace(value: str, join_with_space: bool = False) -> str:
    if not value:
        return ""
    if "\n" in value:
        separator = " " if join_with_space else ", "
        value = re.sub(r"\s*\n\s*", separator, value)
    return re.sub(r"[ \t]+", " ", value).strip().rstrip(",")


_SHORT_CERT_TOKENS = (
    "BOSIET",
    "FOET",
    "CA-EBS",
    "CA EBS",
    "OGUK",
    "GWO",
    "STCW",
    "MIST",
    "H2S",
    "HUET",
    "MMO",
    "PSO",
    "PAMGUARD",
    "JNCC",
    "NEBOSH",
    "IADC",
    "IMCA",
    "IOGP",
    "ISO 45001",
    "ISO 14001",
    "EOD",
    "UXO",
)


def _short_cert_name(name: str) -> str | None:
    upper = name.upper()
    for token in _SHORT_CERT_TOKENS:
        if token in upper:
            return token
    return None


def _year_to_iso(year: str | None) -> str | None:
    if not year:
        return None
    match = re.search(r"\b(19|20)\d{2}\b", year)
    return f"{match.group(0)}-01-01" if match else None
