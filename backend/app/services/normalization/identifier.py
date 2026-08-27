import re
from typing import Optional


class IdentifierNormalizer:
    """Conservative normalizer for property cadastral and deed identifiers."""

    @classmethod
    def normalize(cls, identifier: Optional[str]) -> Optional[str]:
        """Normalize identifier preserving meaningful slash, hyphen, and dot punctuation."""
        if not identifier or not identifier.strip():
            return None

        # 1. Strip and lowercase
        val = identifier.strip().lower()

        # 2. Collapse internal whitespace around slashes, hyphens, and dots
        val = re.sub(r"\s*/\s*", "/", val)
        val = re.sub(r"\s*-\s*", "-", val)
        val = re.sub(r"\s*\.\s*", ".", val)

        # 3. Collapse multiple whitespace
        val = re.sub(r"\s+", " ", val).strip()

        return val or None
