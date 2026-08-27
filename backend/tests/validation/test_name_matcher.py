import pytest

from app.models.enums import MatchStatus
from app.services.matching.name_matcher import NameMatcher


def test_name_matcher_exact_and_permutations() -> None:
    """Verify exact name matches and token order permutations."""
    # Exact match
    res_exact = NameMatcher.match_names("Ramesh Kumar", "Ramesh Kumar")
    assert res_exact.match_status == MatchStatus.MATCH
    assert res_exact.similarity_score == 1.0

    # Token permutation
    res_perm = NameMatcher.match_names("Kumar Ramesh", "Ramesh Kumar")
    assert res_perm.match_status == MatchStatus.MATCH
    assert res_perm.similarity_score >= 0.95


def test_name_matcher_abbreviations_and_mismatches() -> None:
    """Verify conservative partial matches and rejection of distinct names."""
    # Initial / abbreviation match
    res_abbr = NameMatcher.match_names("Ramesh K.", "Ramesh Kumar")
    assert res_abbr.match_status == MatchStatus.PARTIAL_MATCH
    assert res_abbr.similarity_score >= 0.75

    # Completely different names
    res_diff = NameMatcher.match_names("Ramesh Kumar", "Suresh Kumar")
    assert res_diff.match_status == MatchStatus.MISMATCH

    # Phonetically similar but legally distinct name
    res_phon = NameMatcher.match_names("Ramesh Kumar", "Rajesh Kumar")
    assert res_phon.match_status == MatchStatus.MISMATCH


def test_multi_owner_set_matching() -> None:
    """Verify multi-owner collection comparisons."""
    # Full set match
    res_full = NameMatcher.match_owner_sets(
        ["Ramesh Kumar", "Suresh Kumar"],
        ["Suresh Kumar", "Ramesh Kumar"],
    )
    assert res_full.overall_status == MatchStatus.MATCH
    assert len(res_full.matched) == 2
    assert len(res_full.document_only) == 0
    assert len(res_full.reference_only) == 0

    # Partial set match (document has extra owner)
    res_part = NameMatcher.match_owner_sets(
        ["Ramesh Kumar", "Anita Kumar"],
        ["Ramesh Kumar"],
    )
    assert res_part.overall_status == MatchStatus.PARTIAL_MATCH
    assert len(res_part.matched) == 1
    assert "Anita Kumar" in res_part.document_only

    # Complete mismatch
    res_mismatch = NameMatcher.match_owner_sets(
        ["Vijay Sharma"],
        ["Ramesh Kumar"],
    )
    assert res_mismatch.overall_status == MatchStatus.MISMATCH
