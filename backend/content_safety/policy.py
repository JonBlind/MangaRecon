from __future__ import annotations

from collections.abc import Iterable


ADULT_GENRE_NAMES = frozenset(
    {
        "Adult",
        "Hentai",
        "Lolicon",
        "Shotacon",
        "Smut",
    }
)

NORMALIZED_ADULT_GENRE_NAMES = frozenset(
    name.casefold() for name in ADULT_GENRE_NAMES
)


def genres_are_adult_content(genre_names: Iterable[str]) -> bool:
    """Return whether any normalized genre marks a title as adult content."""
    return any(
        name.strip().casefold() in NORMALIZED_ADULT_GENRE_NAMES
        for name in genre_names
    )
