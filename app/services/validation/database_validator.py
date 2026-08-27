from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import logger
from app.models.enums import (
    CandidateSelectionStatus,
    MatchStatus,
    MismatchReason,
    ValidationStatus,
)
from app.models.property_profile import PropertyProfile
from app.models.reference_property import ReferenceProperty
from app.models.validation import ValidationRun
from app.models.validation_candidate import ValidationCandidate
from app.models.validation_result import ValidationResult
from app.services.matching.name_matcher import NameMatcher
from app.services.normalization.identifier import IdentifierNormalizer
from app.services.validation.base import Validator
from app.services.validation.reference_db_provider import ReferencePropertyProvider
from app.services.validation.rules import (
    AdministrativeLocationRule,
    AreaRule,
    IdentifierRule,
    NameRule,
)


class DatabaseValidator(Validator):
    """Orchestrates candidate lookup, multi-attribute scoring, candidate selection, and rule evaluation against authoritative database records."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.provider = ReferencePropertyProvider(db)

    def calculate_candidate_score(
        self, profile: PropertyProfile, ref: ReferenceProperty
    ) -> float:
        """Deterministic score calculating candidate correspondence strength."""
        score = 0.0

        # 1. Parcel Number exact match (+100)
        if profile.parcel_number and ref.parcel_number:
            if IdentifierNormalizer.normalize(
                profile.parcel_number
            ) == IdentifierNormalizer.normalize(ref.parcel_number):
                score += 100.0

        # 2. Survey Number exact match (+80)
        if profile.survey_number and ref.survey_number:
            if IdentifierNormalizer.normalize(
                profile.survey_number
            ) == IdentifierNormalizer.normalize(ref.survey_number):
                score += 80.0

        # 3. Plot Number exact match (+60)
        if profile.plot_number and ref.plot_number:
            if IdentifierNormalizer.normalize(
                profile.plot_number
            ) == IdentifierNormalizer.normalize(ref.plot_number):
                score += 60.0

        # 4. Registration Number exact match (+70)
        if profile.registration_number and ref.registration_number:
            if IdentifierNormalizer.normalize(
                profile.registration_number
            ) == IdentifierNormalizer.normalize(ref.registration_number):
                score += 70.0

        # 5. Deed Number exact match (+50)
        if profile.deed_number and ref.deed_number:
            if IdentifierNormalizer.normalize(
                profile.deed_number
            ) == IdentifierNormalizer.normalize(ref.deed_number):
                score += 50.0

        # 6. Owner correspondence (+40 * similarity)
        doc_owners = [o.name for o in profile.owners if o.name]
        ref_owners = [o.name for o in ref.owners if o.name]
        if doc_owners and ref_owners:
            owner_res = NameMatcher.match_owner_sets(doc_owners, ref_owners)
            score += 40.0 * owner_res.overall_score

        # 7. Administrative location match (+20 each)
        if profile.district and ref.district:
            if " ".join(profile.district.lower().split()) == " ".join(
                ref.district.lower().split()
            ):
                score += 20.0

        if profile.village and ref.village:
            if " ".join(profile.village.lower().split()) == " ".join(
                ref.village.lower().split()
            ):
                score += 20.0

        return round(score, 2)

    async def find_candidates(
        self, profile: PropertyProfile
    ) -> List[Tuple[ReferenceProperty, float]]:
        """Search and rank potential reference property candidates."""
        candidates_map: Dict[uuid.UUID, ReferenceProperty] = {}

        # 1. Search by parcel number
        if profile.parcel_number:
            for p in await self.provider.find_by_parcel_number(profile.parcel_number):
                candidates_map[p.id] = p

        # 2. Search by survey and plot
        if profile.survey_number:
            for p in await self.provider.find_by_survey_and_plot(
                profile.survey_number, profile.plot_number
            ):
                candidates_map[p.id] = p

        # 3. Search by registration number
        if profile.registration_number:
            for p in await self.provider.find_by_registration_number(
                profile.registration_number
            ):
                candidates_map[p.id] = p

        # 4. Search by deed number
        if profile.deed_number:
            for p in await self.provider.find_by_deed_number(profile.deed_number):
                candidates_map[p.id] = p

        # Score and rank candidates
        ranked: List[Tuple[ReferenceProperty, float]] = []
        for ref_prop in candidates_map.values():
            s = self.calculate_candidate_score(profile, ref_prop)
            ranked.append((ref_prop, s))

        ranked.sort(key=lambda x: x[1], reverse=True)
        return ranked

    async def validate(self, profile: PropertyProfile) -> List[ValidationResult]:
        """Base implementation: delegated to validate_run."""
        raise NotImplementedError("Use validate_run with a persistent ValidationRun instance.")

    async def validate_run(
        self, run: ValidationRun, profile: PropertyProfile
    ) -> Tuple[ValidationStatus, List[ValidationResult], List[ValidationCandidate]]:
        """Execute full reference validation lifecycle for a ValidationRun."""
        run.started_at = datetime.now(timezone.utc)
        run.status = ValidationStatus.RUNNING

        # 1. Candidate search & scoring
        ranked_candidates = await self.find_candidates(profile)

        # 2. Case: No candidates found
        if not ranked_candidates:
            run.status = ValidationStatus.FAILED
            run.completed_at = datetime.now(timezone.utc)
            not_found_result = ValidationResult(
                id=uuid.uuid4(),
                validation_run_id=run.id,
                field_name="reference_property",
                document_value=profile.property_identifier or profile.survey_number,
                reference_value=None,
                match_status=MatchStatus.NOT_FOUND,
                match_score=0.0,
                mismatch_reason=MismatchReason.REFERENCE_RECORD_NOT_FOUND.value,
            )
            return ValidationStatus.FAILED, [not_found_result], []

        # 3. Case: Candidates found -> Selection resolution
        candidates_to_save: List[ValidationCandidate] = []
        selected_reference: Optional[ReferenceProperty] = None

        top_ref, top_score = ranked_candidates[0]

        if len(ranked_candidates) == 1:
            if top_score >= 50.0:
                selected_reference = top_ref
                candidates_to_save.append(
                    ValidationCandidate(
                        id=uuid.uuid4(),
                        validation_run_id=run.id,
                        source_id=top_ref.source_id,
                        source_record_id=top_ref.source_record_id,
                        match_score=top_score,
                        selection_status=CandidateSelectionStatus.SELECTED,
                    )
                )
            else:
                candidates_to_save.append(
                    ValidationCandidate(
                        id=uuid.uuid4(),
                        validation_run_id=run.id,
                        source_id=top_ref.source_id,
                        source_record_id=top_ref.source_record_id,
                        match_score=top_score,
                        selection_status=CandidateSelectionStatus.REJECTED,
                    )
                )
        else:
            # Multiple candidates -> check margin
            second_ref, second_score = ranked_candidates[1]
            if top_score >= 80.0 and (top_score - second_score) >= 30.0:
                selected_reference = top_ref
                candidates_to_save.append(
                    ValidationCandidate(
                        id=uuid.uuid4(),
                        validation_run_id=run.id,
                        source_id=top_ref.source_id,
                        source_record_id=top_ref.source_record_id,
                        match_score=top_score,
                        selection_status=CandidateSelectionStatus.SELECTED,
                    )
                )
                for r, s in ranked_candidates[1:]:
                    candidates_to_save.append(
                        ValidationCandidate(
                            id=uuid.uuid4(),
                            validation_run_id=run.id,
                            source_id=r.source_id,
                            source_record_id=r.source_record_id,
                            match_score=s,
                            selection_status=CandidateSelectionStatus.REJECTED,
                        )
                    )
            else:
                # Ambiguous match
                for r, s in ranked_candidates:
                    candidates_to_save.append(
                        ValidationCandidate(
                            id=uuid.uuid4(),
                            validation_run_id=run.id,
                            source_id=r.source_id,
                            source_record_id=r.source_record_id,
                            match_score=s,
                            selection_status=CandidateSelectionStatus.AMBIGUOUS,
                        )
                    )

        if not selected_reference:
            run.status = ValidationStatus.FAILED
            run.completed_at = datetime.now(timezone.utc)
            ambiguous_result = ValidationResult(
                id=uuid.uuid4(),
                validation_run_id=run.id,
                field_name="candidate_selection",
                document_value=profile.property_identifier or profile.survey_number,
                reference_value=f"{len(ranked_candidates)} ambiguous candidates",
                match_status=MatchStatus.MISMATCH,
                match_score=0.0,
                mismatch_reason=MismatchReason.AMBIGUOUS_MATCH.value,
            )
            return ValidationStatus.FAILED, [ambiguous_result], candidates_to_save

        # 4. Evaluate comparison rules against selected reference record
        run.source_id = selected_reference.source_id
        run.dataset_version = selected_reference.dataset_version
        run.validator_version = "1.0"

        results: List[ValidationResult] = []
        results.extend(IdentifierRule.evaluate(run.id, profile, selected_reference))
        results.extend(NameRule.evaluate(run.id, profile, selected_reference))
        results.extend(AreaRule.evaluate(run.id, profile, selected_reference))
        results.extend(
            AdministrativeLocationRule.evaluate(run.id, profile, selected_reference)
        )

        # 5. Determine overall run status
        has_critical_mismatch = any(
            r.match_status == MatchStatus.MISMATCH for r in results
        )
        has_critical_match = any(
            r.match_status == MatchStatus.MATCH and r.field_name in ("survey_number", "parcel_number", "registration_number")
            for r in results
        )

        if not has_critical_mismatch and has_critical_match:
            run.status = ValidationStatus.PASSED
        else:
            run.status = ValidationStatus.FAILED

        run.completed_at = datetime.now(timezone.utc)
        return run.status, results, candidates_to_save
