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

# Explicit series are outside the catalog. The broader Adult label can also
# denote mature nonsexual works, so keep it behind the existing opt-in filter
# rather than excluding it from ingestion.
EXPLICIT_GENRE_NAMES = frozenset(
    {"Hentai", "Lolicon", "Shotacon", "Smut"}
)
RESTRICTED_INGESTION_GENRE_NAMES = EXPLICIT_GENRE_NAMES

NORMALIZED_ADULT_GENRE_NAMES = frozenset(
    name.casefold() for name in ADULT_GENRE_NAMES
)
NORMALIZED_EXPLICIT_GENRE_NAMES = frozenset(
    name.casefold() for name in EXPLICIT_GENRE_NAMES
)


def genres_are_adult_content(genre_names: Iterable[str]) -> bool:
    """Return whether any normalized genre marks a title as adult content."""
    return any(
        name.strip().casefold() in NORMALIZED_ADULT_GENRE_NAMES
        for name in genre_names
    )


class CatalogContentExcluded(ValueError):
    """A series cannot be added under the catalog's content policy."""

    def __init__(self) -> None:
        super().__init__("Explicit genre is excluded from the catalog.")


def check_catalog_ingestion_genres(genre_names: Iterable[str]) -> None:
    """Reject explicit genres while allowing Adult titles behind opt-in."""
    normalized = {name.strip().casefold() for name in genre_names}

    if normalized.intersection(NORMALIZED_EXPLICIT_GENRE_NAMES):
        raise CatalogContentExcluded()
