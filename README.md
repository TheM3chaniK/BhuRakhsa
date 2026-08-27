# Property Document Verification System — Backend API

Production-grade, evidence-grounded property document verification backend. The platform provides automated document processing via DeepSeek OCR on Ollama, structured field extraction with bounding-box evidence links, canonical property profiling, authoritative government registry matching, PostGIS spatial/GIS validation, deterministic mismatch scoring, explainable risk assessment, role-based jurisdictional officer review workflows, supplementary proof cycles, terminal decision lifecycle management, immutable audit logging, outbox event delivery, and comprehensive administrative dashboards.

---

## 1. System Architecture & Lifecycle

```text
                                  +-----------------------+
                                  |     Civilian User     |
                                  +-----------+-----------+
                                              | (Create Case / Upload Docs)
                                              v
+-----------------------------------------------------------------------------------------+
|                                    INGESTION PIPELINE                                   |
|                                                                                         |
|  Uploaded PDF / Images                                                                 |
|         │                                                                               |
|         ▼                                                                               |
|  Page Splitting & Preprocessing (PyMuPDF, 300 DPI, Grayscale, Contrast Enhancement)     |
|         │                                                                               |
|         ▼                                                                               |
|  DeepSeek OCR via Local Ollama Inference (Model: deepseek-ocr)                          |
|         │                                                                               |
|         ▼                                                                               |
|  Structured Field Extraction & Evidence Bounding Boxes (Pydantic Validation)           |
+---------------------------------------------+-------------------------------------------+
                                              │
                                              ▼
+-----------------------------------------------------------------------------------------+
|                                  VALIDATION & RISK ENGINE                               |
|                                                                                         |
|  Canonical Property Profile Formed (Versioned Aggregation of Document Fields)          |
|         │                                                                               |
|         ├──► Authoritative Government Registry Matching (Name, Identifiers, Area)      |
|         │                                                                               |
|         └──► PostGIS Spatial Validation (Point-in-Polygon, Boundary Area Tolerance)     |
|         │                                                                               |
|         ▼                                                                               |
|  Mismatch Engine (Discrepancy Severity Classification & Weight Assignment)             |
|         │                                                                               |
|         ▼                                                                               |
|  Explainable Risk Scoring (Deterministic Composite Risk Score & Risk Tiering)          |
+---------------------------------------------+-------------------------------------------+
                                              │
                                              ▼
+-----------------------------------------------------------------------------------------+
|                                 JURISDICTION REVIEW WORKFLOW                            |
|                                                                                         |
|  Area Officer Queue (Strictly Scoped to Assigned Geographic Area)                       |
|         │                                                                               |
|         ├──► REQUEST_PROOF ──► Case: PROOF_REQUIRED ──► Civilian Supplementary Ingestion|
|         │                                                 │                             |
|         │                                                 ▼                             |
|         │                                        Automated Revalidation                 |
|         │                                        (New Profile Version & Risk)           |
|         │                                                 │                             |
|         │                                                 ▼                             |
|         │                                        Return to Officer Queue                |
|         │                                                                               |
|         ├──► APPROVE ───────► Case: APPROVED (Terminal Immutable State)                |
|         │                                                                               |
|         └──► REJECT  ───────► Case: REJECTED (Terminal Immutable State)                |
+---------------------------------------------+-------------------------------------------+
                                              │
                                              ▼
+-----------------------------------------------------------------------------------------+
|                              AUDIT, OUTBOX & NOTIFICATIONS                              |
|                                                                                         |
|  Immutable FinalDecision Snapshot & Append-Only Audit Event Logged in Same DB Tx        |
|         │                                                                               |
|         ▼                                                                               |
|  Transactional Outbox Event Queued (At-Least-Once Delivery with Retry & Backoff)        |
|         │                                                                               |
|         ▼                                                                               |
|  Outbox Worker Dispatches Notifications to Civilian & Area Officers                     |
+-----------------------------------------------------------------------------------------+
```

---

## 2. API Endpoints Reference

### Public Endpoints
| Method | Endpoint | Description | Auth Required |
|---|---|---|---|
| `GET` | `/health` | Minimal public system health status (`{"status": "ok"}`) | None |
| `POST` | `/api/v1/auth/register` | Register new civilian account | None |
| `POST` | `/api/v1/auth/login` | Authenticate user and issue JWT access & refresh tokens | None (Rate Limited) |
| `POST` | `/api/v1/auth/refresh` | Rotate JWT access and refresh tokens | Refresh Token |
| `POST` | `/api/v1/auth/logout` | Revoke refresh token and invalidate session | Bearer Token |

### User & Self Endpoints
| Method | Endpoint | Description | Scopes |
|---|---|---|---|
| `GET` | `/api/v1/users/me` | Retrieve profile and assigned area details | Authenticated |
| `PATCH` | `/api/v1/users/me` | Update name and phone number | Authenticated |
| `POST` | `/api/v1/users/me/change-password` | Change user account password | Authenticated |
| `GET` | `/api/v1/notifications` | List user notifications with unread filter | Authenticated |
| `GET` | `/api/v1/notifications/unread-count` | Get total count of unread notifications | Authenticated |
| `POST` | `/api/v1/notifications/{id}/read` | Mark individual notification as read | Authenticated |
| `POST` | `/api/v1/notifications/read-all` | Mark all notifications as read | Authenticated |

### Case & Document Verification Endpoints
| Method | Endpoint | Description | Scopes |
|---|---|---|---|
| `POST` | `/api/v1/cases` | Create a new verification case in DRAFT status | Civilian |
| `GET` | `/api/v1/cases` | List cases (role-scoped: Civilian sees own, Officer sees assigned areas) | Authenticated |
| `GET` | `/api/v1/cases/{case_id}` | Retrieve case details with access verification | Authenticated |
| `PATCH` | `/api/v1/cases/{case_id}` | Update title, description, or area of DRAFT case | Civilian Owner |
| `POST` | `/api/v1/cases/{case_id}/submit` | Submit case for automated processing | Civilian Owner |
| `GET` | `/api/v1/cases/{case_id}/status` | Get simplified case status milestones | Authenticated |
| `POST` | `/api/v1/documents` | Upload PDF or image document | Civilian Owner |
| `GET` | `/api/v1/documents/{doc_id}` | Retrieve document metadata | Authorized |
| `GET` | `/api/v1/documents/{doc_id}/download` | Securely download document bytes | Authorized |
| `DELETE` | `/api/v1/documents/{doc_id}` | Delete document from draft case | Civilian Owner |
| `GET` | `/api/v1/cases/{case_id}/final-decision` | Retrieve immutable final decision snapshot | Authorized |
| `GET` | `/api/v1/cases/{case_id}/audit` | Retrieve audit trail (milestone view for Civilian, full for Officer/Admin) | Authorized |

### Area Officer Endpoints
| Method | Endpoint | Description | Scopes |
|---|---|---|---|
| `GET` | `/api/v1/officer/dashboard` | Aggregated dashboard metrics for officer's assigned jurisdiction | Area Officer |
| `GET` | `/api/v1/officer/cases` | Search and filter cases strictly in officer's jurisdiction | Area Officer |
| `GET` | `/api/v1/officer/areas` | List geographical areas assigned to calling officer | Area Officer |
| `GET` | `/api/v1/review/queue` | Paginated review queue of ready cases in assigned areas | Area Officer |
| `POST` | `/api/v1/cases/{case_id}/review/start` | Acquire review lock and transition case to UNDER_REVIEW | Area Officer |
| `POST` | `/api/v1/cases/{case_id}/review/decision` | Submit determination (`APPROVE`, `REJECT`, `REQUEST_PROOF`) | Area Officer |
| `POST` | `/api/v1/cases/{case_id}/proof-requests` | Issue supplementary proof request | Area Officer |
| `POST` | `/api/v1/proof-requests/{id}/accept` | Accept civilian proof and resolve request | Area Officer |
| `POST` | `/api/v1/proof-requests/{id}/reject` | Reject civilian proof | Area Officer |

### Super Admin Endpoints
| Method | Endpoint | Description | Scopes |
|---|---|---|---|
| `GET` | `/api/v1/admin/dashboard` | Consolidated system metrics (areas, users, cases, risk, processing) | Super Admin |
| `GET` | `/api/v1/admin/cases` | Search cases across all areas with sorting and filters | Super Admin |
| `GET` | `/api/v1/admin/cases/{case_id}` | Complete 360-degree operational dossier across all intelligence layers | Super Admin |
| `GET` | `/api/v1/admin/areas` | List geographical areas with pagination and search | Super Admin |
| `POST` | `/api/v1/admin/areas` | Provision new geographical area with unique code | Super Admin |
| `GET` | `/api/v1/admin/areas/{id}` | Get geographical area details | Super Admin |
| `PATCH` | `/api/v1/admin/areas/{id}` | Update area (active conflict protection on deactivation) | Super Admin |
| `GET` | `/api/v1/admin/officers` | List all Area Officers with assignments | Super Admin |
| `GET` | `/api/v1/admin/officers/{id}` | Retrieve individual officer profile and assigned areas | Super Admin |
| `POST` | `/api/v1/admin/officers` | Provision new Area Officer account | Super Admin |
| `PATCH` | `/api/v1/admin/officers/{id}` | Update officer profile or active status | Super Admin |
| `POST` | `/api/v1/admin/officers/{id}/areas/{area_id}` | Assign officer to geographical area | Super Admin |
| `DELETE` | `/api/v1/admin/officers/{id}/areas/{area_id}` | Unassign officer from geographical area | Super Admin |
| `POST` | `/api/v1/admin/officers/{id}/demote` | Demote officer to civilian (clears assignments & revokes tokens) | Super Admin |
| `GET` | `/api/v1/admin/statistics/{cases,risk,reviews,proofs,processing,officers}` | Multi-dimensional statistical aggregation endpoints | Super Admin |
| `GET` | `/api/v1/admin/queues` | Live background queue depth monitoring | Super Admin |
| `GET` | `/api/v1/admin/jobs/failed` | List failed background tasks with error messages | Super Admin |
| `POST` | `/api/v1/admin/jobs/{id}/retry` | Manually reset failed job to PENDING and record audit event | Super Admin |
| `GET` | `/api/v1/admin/system/health` | Comprehensive multi-component health report | Super Admin |

---

## 3. Security & Production Hardening

1. **Security Headers Middleware**:
   * `X-Request-ID`: Correlation ID injected and propagated across all requests.
   * `X-Content-Type-Options: nosniff`: Prevents MIME-type sniffing.
   * `X-Frame-Options: DENY`: Prevents clickjacking attacks.
   * `Referrer-Policy: strict-origin-when-cross-origin`: Restricts referrer exposure.
   * `Content-Security-Policy: default-src 'self'`: Restricts unauthorized script execution.

2. **Sliding-Window Rate Limiting**:
   * Sensitive endpoints (`/auth/login`, `/auth/register`, `/auth/refresh`) are protected by an in-memory sliding-window rate limiter returning `429 Too Many Requests` when limits are exceeded.

3. **Deterministic Case State Machine**:
   * All state transitions are strictly governed by `CaseStateMachine`.
   * Out-of-sequence transitions (e.g., `DRAFT -> APPROVED`) are rejected with `400 Bad Request`.
   * Terminal states (`APPROVED`, `REJECTED`) are immutable and reject further modifications with `409 Conflict`.

4. **Input Validation & Sanitization**:
   * Pagination is strictly bounded (`1 <= page_size <= 100`, `page >= 1`).
   * Sorting is protected by an explicit allowlist (`created_at`, `updated_at`, `status`, `risk_level`).
   * Document uploads enforce magic bytes validation, allowed extensions, and path traversal prevention (`../../` sanitization).

---

## 4. Running and Testing

### Setup Environment
```bash
# 1. Start PostgreSQL + PostGIS Container
docker compose up -d

# 2. Run Database Migrations
.venv/bin/alembic upgrade head

# 3. Start FastApi Server
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Running Test Suite
```bash
.venv/bin/pytest -v
```
All 154+ tests pass cleanly covering unit tests, negative security cases, RBAC & jurisdictional isolation, concurrency, and full end-to-end integration workflows.
