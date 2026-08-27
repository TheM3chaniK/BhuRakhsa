from enum import Enum


class UserRole(str, Enum):
    """Application user access control roles."""

    CIVILIAN = "civilian"
    AREA_OFFICER = "area_officer"
    SUPER_ADMIN = "super_admin"


class CaseStatus(str, Enum):
    """Lifecycle statuses of a property verification case."""

    DRAFT = "draft"
    SUBMITTED = "submitted"
    PROCESSING = "processing"
    EXTRACTED = "extracted"
    VALIDATING = "validating"
    REVIEW_READY = "review_ready"
    UNDER_REVIEW = "under_review"
    PROOF_REQUIRED = "proof_required"
    APPROVED = "approved"
    REJECTED = "rejected"
    CLOSED = "closed"
    FAILED = "failed"


class RiskLevel(str, Enum):
    """Risk assessment severity and review priority classification."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class ReviewStatus(str, Enum):
    """Execution state of an officer case verification review."""

    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class OfficerDecision(str, Enum):
    """Final decision submitted by an authorized Area Officer."""

    APPROVE = "approve"
    REJECT = "reject"
    REQUEST_PROOF = "request_proof"


class ReviewAction(str, Enum):
    """Audit action categories performed during the review lifecycle."""

    REVIEW_STARTED = "review_started"
    DECISION_SUBMITTED = "decision_submitted"
    REVIEW_COMPLETED = "review_completed"


class ProofRequestStatus(str, Enum):
    """Lifecycle state of an officer proof request."""

    OPEN = "open"
    SUBMITTED = "submitted"
    UNDER_REVIEW = "under_review"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class ProofType(str, Enum):
    """Category of additional documentary evidence requested."""

    OWNERSHIP_DOCUMENT = "ownership_document"
    SALE_DEED = "sale_deed"
    TITLE_DOCUMENT = "title_document"
    TAX_RECEIPT = "tax_receipt"
    SURVEY_DOCUMENT = "survey_document"
    REGISTRATION_DOCUMENT = "registration_document"
    IDENTITY_DOCUMENT = "identity_document"
    ADDRESS_PROOF = "address_proof"
    OTHER = "other"


class ProofSubmissionStatus(str, Enum):
    """Processing and validation state of a civilian proof upload."""

    SUBMITTED = "submitted"
    PROCESSING = "processing"
    PROCESSED = "processed"
    FAILED = "failed"


class ProofRequestAction(str, Enum):
    """Audit event action types for proof request lifecycle."""

    CREATED = "created"
    SUBMITTED = "submitted"
    PROCESSING_STARTED = "processing_started"
    PROCESSING_COMPLETED = "processing_completed"
    PROCESSING_FAILED = "processing_failed"
    UNDER_REVIEW = "under_review"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class AuditActorType(str, Enum):
    """Category of actor initiating an audited action."""

    USER = "user"
    SYSTEM = "system"


class AuditAction(str, Enum):
    """Controlled domain audit action types across case lifecycle."""

    CASE_CREATED = "case_created"
    CASE_SUBMITTED = "case_submitted"
    DOCUMENT_UPLOADED = "document_uploaded"
    OCR_STARTED = "ocr_started"
    OCR_COMPLETED = "ocr_completed"
    OCR_FAILED = "ocr_failed"
    EXTRACTION_STARTED = "extraction_started"
    EXTRACTION_COMPLETED = "extraction_completed"
    VALIDATION_STARTED = "validation_started"
    VALIDATION_COMPLETED = "validation_completed"
    VALIDATION_FAILED = "validation_failed"
    RISK_CALCULATED = "risk_calculated"
    REVIEW_STARTED = "review_started"
    REVIEW_DECISION_SUBMITTED = "review_decision_submitted"
    PROOF_REQUEST_CREATED = "proof_request_created"
    PROOF_SUBMITTED = "proof_submitted"
    PROOF_ACCEPTED = "proof_accepted"
    PROOF_REJECTED = "proof_rejected"
    PROOF_CANCELLED = "proof_cancelled"
    FINAL_DECISION_CREATED = "final_decision_created"
    CASE_APPROVED = "case_approved"
    CASE_REJECTED = "case_rejected"
    NOTIFICATION_CREATED = "notification_created"
    NOTIFICATION_SENT = "notification_sent"
    NOTIFICATION_FAILED = "notification_failed"


class OutboxEventStatus(str, Enum):
    """State of an outbox domain event queue item."""

    PENDING = "pending"
    PROCESSING = "processing"
    PROCESSED = "processed"
    FAILED = "failed"


class NotificationStatus(str, Enum):
    """Delivery status of a user notification."""

    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    READ = "read"


class NotificationType(str, Enum):
    """Category of notification message."""

    PROOF_REQUESTED = "proof_requested"
    PROOF_SUBMITTED = "proof_submitted"
    PROOF_ACCEPTED = "proof_accepted"
    PROOF_REJECTED = "proof_rejected"
    CASE_APPROVED = "case_approved"
    CASE_REJECTED = "case_rejected"
    CASE_STATUS_CHANGED = "case_status_changed"


class NotificationChannel(str, Enum):
    """Delivery transport channel for notifications."""

    IN_APP = "in_app"


class DocumentStatus(str, Enum):
    """Ingestion and OCR processing state of an uploaded document."""

    UPLOADED = "uploaded"
    QUEUED = "queued"
    PROCESSING = "processing"
    PROCESSED = "processed"
    FAILED = "failed"


class ProcessingStatus(str, Enum):
    """Execution status of an asynchronous document processing job."""

    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ExtractionStatus(str, Enum):
    """Status indicator for structured field extraction from document OCR."""

    EXTRACTED = "extracted"
    UNCERTAIN = "uncertain"
    NOT_FOUND = "not_found"


class OwnershipType(str, Enum):
    """Legal ownership relationship category."""

    INDIVIDUAL = "individual"
    JOINT = "joint"
    ORGANIZATION = "organization"
    UNKNOWN = "unknown"


class ProfileStatus(str, Enum):
    """Lifecycle state of a canonical property profile."""

    DRAFT = "draft"
    EXTRACTED = "extracted"
    VALIDATION_PENDING = "validation_pending"
    VALIDATED = "validated"


class ValidationType(str, Enum):
    """Category of external reference validation."""

    DATABASE = "database"
    GIS = "gis"


class ValidationStatus(str, Enum):
    """Execution status of a validation run."""

    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    PASSED_WITH_LIMITATIONS = "passed_with_limitations"
    FAILED = "failed"
    ERROR = "error"


class MatchStatus(str, Enum):
    """Outcome comparison status between document field and reference source."""

    MATCH = "match"
    PARTIAL_MATCH = "partial_match"
    MISMATCH = "mismatch"
    NOT_FOUND = "not_found"
    NOT_CHECKED = "not_checked"


class CandidateSelectionStatus(str, Enum):
    """Selection outcome for a candidate reference record during validation search."""

    CANDIDATE = "candidate"
    SELECTED = "selected"
    REJECTED = "rejected"
    AMBIGUOUS = "ambiguous"


class BoundaryType(str, Enum):
    """Administrative spatial jurisdiction boundary hierarchy level."""

    DISTRICT = "district"
    SUBDIVISION = "subdivision"
    VILLAGE = "village"
    MOUZA = "mouza"
    WARD = "ward"


class CoordinateSource(str, Enum):
    """Origin provenance for geographic coordinate points."""

    DOCUMENT = "document"
    USER = "user"
    REFERENCE_DATABASE = "reference_database"
    GIS = "gis"


class MismatchSource(str, Enum):
    """Provenance pipeline stage producing a discrepancy."""

    EXTRACTION = "extraction"
    DATABASE = "database"
    GIS = "gis"


class MismatchSeverity(str, Enum):
    """Severity tier indicating validation discrepancy impact."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RiskAssessmentStatus(str, Enum):
    """Lifecycle execution status of a risk assessment job."""

    PENDING = "pending"
    CALCULATING = "calculating"
    COMPLETED = "completed"
    FAILED = "failed"


class MismatchType(str, Enum):
    """Controlled canonical discrepancy classifications."""

    # Cadastral & Identity (Database)
    OWNER_MISMATCH = "owner_mismatch"
    SURVEY_NUMBER_MISMATCH = "survey_number_mismatch"
    PLOT_NUMBER_MISMATCH = "plot_number_mismatch"
    PARCEL_NUMBER_MISMATCH = "parcel_number_mismatch"
    REGISTRATION_NUMBER_MISMATCH = "registration_number_mismatch"
    DEED_NUMBER_MISMATCH = "deed_number_mismatch"

    # Surface Area
    AREA_MISMATCH = "area_mismatch"
    REFERENCE_GIS_AREA_MISMATCH = "reference_gis_area_mismatch"
    DOCUMENT_GIS_AREA_MISMATCH = "document_gis_area_mismatch"

    # Administrative Location
    DISTRICT_MISMATCH = "district_mismatch"
    SUBDIVISION_MISMATCH = "subdivision_mismatch"
    VILLAGE_MISMATCH = "village_mismatch"
    MOUZA_MISMATCH = "mouza_mismatch"
    WARD_MISMATCH = "ward_mismatch"

    # Spatial / GIS
    PARCEL_NOT_FOUND = "parcel_not_found"
    PARCEL_GEOMETRY_NOT_FOUND = "parcel_geometry_not_found"
    INVALID_PARCEL_GEOMETRY = "invalid_parcel_geometry"
    POINT_OUTSIDE_PARCEL = "point_outside_parcel"
    DISTRICT_LOCATION_MISMATCH = "district_location_mismatch"
    VILLAGE_LOCATION_MISMATCH = "village_location_mismatch"

    # Extraction & Ambiguity
    MULTIPLE_REFERENCE_CANDIDATES = "multiple_reference_candidates"
    EXTRACTION_CONFLICT = "extraction_conflict"


class MismatchReason(str, Enum):
    """Controlled taxonomy of validation discrepancy and failure reasons."""

    # Database validation reasons
    OWNER_MISMATCH = "OWNER_MISMATCH"
    SURVEY_NUMBER_MISMATCH = "SURVEY_NUMBER_MISMATCH"
    PLOT_NUMBER_MISMATCH = "PLOT_NUMBER_MISMATCH"
    PARCEL_NUMBER_MISMATCH = "PARCEL_NUMBER_MISMATCH"
    REGISTRATION_NUMBER_MISMATCH = "REGISTRATION_NUMBER_MISMATCH"
    DEED_NUMBER_MISMATCH = "DEED_NUMBER_MISMATCH"
    AREA_MISMATCH = "AREA_MISMATCH"
    DISTRICT_MISMATCH = "DISTRICT_MISMATCH"
    VILLAGE_MISMATCH = "VILLAGE_MISMATCH"
    MOUZA_MISMATCH = "MOUZA_MISMATCH"
    WARD_MISMATCH = "WARD_MISMATCH"
    REFERENCE_RECORD_NOT_FOUND = "REFERENCE_RECORD_NOT_FOUND"
    DOCUMENT_VALUE_NOT_FOUND = "DOCUMENT_VALUE_NOT_FOUND"
    UNSUPPORTED_UNIT = "UNSUPPORTED_UNIT"
    AMBIGUOUS_MATCH = "AMBIGUOUS_MATCH"

    # Spatial / GIS validation reasons
    PARCEL_NOT_FOUND = "PARCEL_NOT_FOUND"
    PARCEL_GEOMETRY_NOT_FOUND = "PARCEL_GEOMETRY_NOT_FOUND"
    INVALID_PARCEL_GEOMETRY = "INVALID_PARCEL_GEOMETRY"
    POINT_OUTSIDE_PARCEL = "POINT_OUTSIDE_PARCEL"
    LOCATION_POINT_NOT_AVAILABLE = "LOCATION_POINT_NOT_AVAILABLE"
    DISTRICT_LOCATION_MISMATCH = "DISTRICT_LOCATION_MISMATCH"
    VILLAGE_LOCATION_MISMATCH = "VILLAGE_LOCATION_MISMATCH"
    REFERENCE_GIS_AREA_MISMATCH = "REFERENCE_GIS_AREA_MISMATCH"
    DOCUMENT_GIS_AREA_MISMATCH = "DOCUMENT_GIS_AREA_MISMATCH"
