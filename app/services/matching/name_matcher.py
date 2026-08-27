from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from app.models.enums import MatchStatus
from app.services.normalization.name import NameNormalizer


@dataclass
class NameMatchResult:
    """Individual name pairwise comparison outcome."""

    document_name: str
    reference_name: str
    match_status: MatchStatus
    similarity_score: float


@dataclass
class OwnerSetMatchResult:
    """Comprehensive multi-owner comparison outcome."""

    matched: List[Tuple[str, str, float]]  # (doc_name, ref_name, score)
    document_only: List[str]
    reference_only: List[str]
    overall_status: MatchStatus
    overall_score: float


class NameMatcher:
    """Conservative name comparator avoiding false identity equivalences."""

    @classmethod
    def match_names(
        cls,
        doc_name: Optional[str],
        ref_name: Optional[str],
    ) -> NameMatchResult:
        """Evaluate single name correspondence conservatively."""
        if not doc_name or not ref_name:
            return NameMatchResult(
                document_name=doc_name or "",
                reference_name=ref_name or "",
                match_status=MatchStatus.NOT_FOUND,
                similarity_score=0.0,
            )

        norm_doc = NameNormalizer.normalize(doc_name) or ""
        norm_ref = NameNormalizer.normalize(ref_name) or ""

        # 1. Exact normalized match
        if norm_doc == norm_ref:
            return NameMatchResult(
                document_name=doc_name,
                reference_name=ref_name,
                match_status=MatchStatus.MATCH,
                similarity_score=1.0,
            )

        tokens_doc = norm_doc.split()
        tokens_ref = norm_ref.split()

        # 2. Token set exact match (order permutation, e.g. "Kumar Ramesh" vs "Ramesh Kumar")
        if set(tokens_doc) == set(tokens_ref):
            return NameMatchResult(
                document_name=doc_name,
                reference_name=ref_name,
                match_status=MatchStatus.MATCH,
                similarity_score=0.98,
            )

        # 3. Check for abbreviation / initial match (e.g. "Ramesh K." vs "Ramesh Kumar")
        if len(tokens_doc) == len(tokens_ref) and len(tokens_doc) >= 2:
            matches = 0
            partial_matches = 0
            for td, tr in zip(tokens_doc, tokens_ref):
                if td == tr:
                    matches += 1
                elif (
                    (len(td) == 1 and tr.startswith(td))
                    or (len(tr) == 1 and td.startswith(tr))
                ):
                    partial_matches += 1

            if matches + partial_matches == len(tokens_doc):
                score = (matches * 1.0 + partial_matches * 0.75) / len(tokens_doc)
                return NameMatchResult(
                    document_name=doc_name,
                    reference_name=ref_name,
                    match_status=MatchStatus.PARTIAL_MATCH,
                    similarity_score=round(score, 2),
                )

        # 4. Subset matching (e.g. "Ramesh Kumar Sharma" vs "Ramesh Kumar")
        common_tokens = set(tokens_doc).intersection(set(tokens_ref))
        if common_tokens and len(common_tokens) >= 2:
            jaccard = len(common_tokens) / len(set(tokens_doc).union(set(tokens_ref)))
            if jaccard >= 0.6:
                return NameMatchResult(
                    document_name=doc_name,
                    reference_name=ref_name,
                    match_status=MatchStatus.PARTIAL_MATCH,
                    similarity_score=round(jaccard, 2),
                )

        # 5. Non-matching
        return NameMatchResult(
            document_name=doc_name,
            reference_name=ref_name,
            match_status=MatchStatus.MISMATCH,
            similarity_score=0.0,
        )

    @classmethod
    def match_owner_sets(
        cls,
        doc_owner_names: List[str],
        ref_owner_names: List[str],
    ) -> OwnerSetMatchResult:
        """Compare two collections of owner names."""
        if not doc_owner_names and not ref_owner_names:
            return OwnerSetMatchResult(
                matched=[],
                document_only=[],
                reference_only=[],
                overall_status=MatchStatus.NOT_CHECKED,
                overall_score=0.0,
            )

        if not doc_owner_names:
            return OwnerSetMatchResult(
                matched=[],
                document_only=[],
                reference_only=ref_owner_names,
                overall_status=MatchStatus.NOT_FOUND,
                overall_score=0.0,
            )

        if not ref_owner_names:
            return OwnerSetMatchResult(
                matched=[],
                document_only=doc_owner_names,
                reference_only=[],
                overall_status=MatchStatus.NOT_FOUND,
                overall_score=0.0,
            )

        matched: List[Tuple[str, str, float]] = []
        unmatched_doc = set(doc_owner_names)
        unmatched_ref = set(ref_owner_names)

        # Perform best matching greedily
        for d in doc_owner_names:
            best_ref = None
            best_res = None
            for r in ref_owner_names:
                if r not in unmatched_ref:
                    continue
                res = cls.match_names(d, r)
                if res.match_status in (MatchStatus.MATCH, MatchStatus.PARTIAL_MATCH):
                    if not best_res or res.similarity_score > best_res.similarity_score:
                        best_res = res
                        best_ref = r

            if best_res and best_ref:
                matched.append((d, best_ref, best_res.similarity_score))
                unmatched_doc.discard(d)
                unmatched_ref.discard(best_ref)

        total_owners = max(len(doc_owner_names), len(ref_owner_names))
        matched_score_sum = sum(score for _, _, score in matched)
        overall_score = round(matched_score_sum / total_owners, 2) if total_owners > 0 else 0.0

        if len(matched) == len(doc_owner_names) == len(ref_owner_names) and all(s >= 0.95 for _, _, s in matched):
            overall_status = MatchStatus.MATCH
        elif matched:
            overall_status = MatchStatus.PARTIAL_MATCH
        else:
            overall_status = MatchStatus.MISMATCH

        return OwnerSetMatchResult(
            matched=matched,
            document_only=sorted(list(unmatched_doc)),
            reference_only=sorted(list(unmatched_ref)),
            overall_status=overall_status,
            overall_score=overall_score,
        )
