from __future__ import annotations

import logging
from dataclasses import dataclass

from rapidfuzz import fuzz, process

logger = logging.getLogger(__name__)

MATCH_THRESHOLD = 60
HIGH_CONFIDENCE_THRESHOLD = 85


@dataclass
class CrewMatch:
    crew_id: str
    name: str
    score: float


class MatchingService:
    """Service for matching documents to existing crew members."""

    async def find_matches(
        self,
        extracted_name: str,
        existing_crew: list[tuple[str, str]],
        limit: int = 3,
        threshold: int = MATCH_THRESHOLD,
    ) -> list[CrewMatch]:
        """Find potential crew member matches for a name."""
        if not extracted_name or not existing_crew:
            return []

        matches = process.extract(
            extracted_name,
            existing_crew,
            scorer=fuzz.WRatio,
            limit=limit,
            score_cutoff=threshold,
        )

        return [
            CrewMatch(
                crew_id=match[0][0],
                name=match[0][1],
                score=round(match[1], 1),
            )
            for match in matches
        ]

    def is_auto_link(self, match: CrewMatch) -> bool:
        """Determine if a match should be auto-linked."""
        return match.score >= HIGH_CONFIDENCE_THRESHOLD

    def is_exact_match(self, match: CrewMatch) -> bool:
        """Determine if a match is exact."""
        return match.score == 100.0


matching_service = MatchingService()
