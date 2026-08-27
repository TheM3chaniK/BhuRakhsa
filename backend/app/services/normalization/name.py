import re
from typing import Optional


class NameNormalizer:
    """Conservative normalizer for individual and co-owner legal names."""

    HONORIFICS = {
        "mr",
        "mrs",
        "ms",
        "miss",
        "shri",
        "shree",
        "smt",
        "shrimati",
        "dr",
        "late",
        "adv",
    }

    @classmethod
    def normalize(cls, name: Optional[str]) -> Optional[str]:
        """Strip honorifics, collapse whitespace, remove punctuation, and case-fold name."""
        if not name or not name.strip():
            return None

        # 1. Lowercase and remove punctuation except spaces
        cleaned = re.sub(r"[^\w\s]", " ", name.lower()).strip()

        # 2. Tokenize and filter honorifics
        tokens = cleaned.split()
        filtered_tokens = []
        for t in tokens:
            t_clean = t.strip()
            if t_clean in cls.HONORIFICS:
                continue
            if t_clean:
                filtered_tokens.append(t_clean)

        if not filtered_tokens:
            filtered_tokens = [t.strip() for t in tokens if t.strip()]

        result = " ".join(filtered_tokens).strip()
        return result or None
