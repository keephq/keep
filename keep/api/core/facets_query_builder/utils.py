import hashlib
from typing import Optional


def _normalize_cel(cel: Optional[str]) -> str:
    """
    Normalize CEL expressions for stable hashing.
    This avoids hash differences due to trivial whitespace.
    """
    if not cel:
        return ""
    # Collapse whitespace and strip
    return " ".join(cel.split())


def get_facet_key(
    facet_property_path: str,
    filter_cel: Optional[str],
    facet_cel: Optional[str],
) -> str:
    """
    Generates a stable, unique key for a facet based on:
    - property path
    - global filter CEL
    - facet-specific CEL

    The key is deterministic and collision-resistant.
    """

    filter_cel_norm = _normalize_cel(filter_cel)
    facet_cel_norm = _normalize_cel(facet_cel)

    # Structured, unambiguous payload
    payload = "\x1f".join(
        [
            f"prop:{facet_property_path}",
            f"filter:{filter_cel_norm}",
            f"facet:{facet_cel_norm}",
        ]
    )

    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()

    # Human-readable + hash
    return f"{facet_property_path}:{digest}"