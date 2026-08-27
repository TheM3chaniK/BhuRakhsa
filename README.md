# BhuRaksha

BhuRaksha is a property document verification platform designed to help civilians submit property-related documents and enable authorized Area Officers to securely review, validate, and make evidence-based verification decisions.

The system combines document OCR, structured data extraction, registry matching, GIS/PostGIS validation, mismatch detection, risk assessment, officer review, proof requests, revalidation, final decisions, audit trails, and notifications.

---

## Table of Contents

* [Overview](#overview)
* [Key Features](#key-features)
* [System Roles](#system-roles)
* [Verification Workflow](#verification-workflow)
* [Architecture](#architecture)
* [Technology Stack](#technology-stack)
* [Requirements](#requirements)
* [Project Structure](#project-structure)
* [Backend Setup](#backend-setup)
* [PostgreSQL + PostGIS Setup](#postgresql--postgis-setup)
* [Ollama + DeepSeek OCR Setup](#ollama--deepseek-ocr-setup)
* [Environment Configuration](#environment-configuration)
* [Database Migrations](#database-migrations)
* [Local Document Storage](#local-document-storage)
* [Starting the Backend](#starting-the-backend)
* [Frontend Setup](#frontend-setup)
* [Running the Complete Application](#running-the-complete-application)
* [API Documentation](#api-documentation)
* [Testing](#testing)
* [Security](#security)
* [Authentication and RBAC](#authentication-and-rbac)
* [GIS and PostGIS](#gis-and-postgis)
* [OCR and Document Processing](#ocr-and-document-processing)
* [Proof and Revalidation Workflow](#proof-and-revalidation-workflow)
* [Audit and Notifications](#audit-and-notifications)
* [SOPS and Encrypted Environment Files](#sops-and-encrypted-environment-files)
* [Troubleshooting](#troubleshooting)
* [Development Workflow](#development-workflow)
* [Production Considerations](#production-considerations)
* [Test Status](#test-status)

---

# Overview

BhuRaksha provides a complete property verification workflow between civilians and government/administrative Area Officers.

The system accepts property documents uploaded by civilians, processes those documents using locally hosted DeepSeek OCR through Ollama, extracts structured property information, compares it against registry and GIS data, calculates mismatches and risk, and routes the case to the appropriate Area Officer.

The Area Officer can review the case, request additional proof when necessary, and ultimately approve or reject the verification request.

The application is designed around jurisdictional isolation, meaning an Area Officer can only access cases belonging to their assigned area.

---

# Key Features

## Civilian Features

* Civilian registration and authentication
* Login/logout
* JWT access and refresh tokens
* Property verification case creation
* Property document upload
* Document status tracking
* OCR processing status
* Verification status tracking
* Proof request handling
* Additional proof submission
* Case history
* Notifications
* Final decision visibility

## Area Officer Features

* Officer authentication
* Area-based jurisdiction
* Officer dashboard
* Case search
* Case filtering
* Case review
* Review locking
* OCR result inspection
* Extracted property information
* Registry validation results
* GIS validation results
* Mismatch analysis
* Risk assessment
* Proof requests
* Proof review
* Revalidation
* Final approval
* Final rejection
* Audit visibility

## Admin Features

* Admin dashboard
* System-wide case search
* User management
* Area management
* Officer management
* Officer-area assignment
* Area deactivation protection
* Statistics
* Queue/job monitoring
* System health
* Administrative operations

## Verification Features

* Document preprocessing
* DeepSeek OCR
* Structured field extraction
* Property/parcel profile generation
* Registry matching
* Name normalization
* Candidate ranking
* GIS validation
* PostGIS spatial rules
* Area comparison
* Spatial mismatch detection
* Risk scoring
* Risk versioning
* Deduplication
* Evidence tracking

## Workflow Features

* Officer review queue
* Review locking
* Proof request workflow
* Proof submission
* Revalidation
* Review cycles
* Final decision
* Decision snapshots
* Terminal state protection
* Immutable decision records
* Audit trail
* Outbox events
* Notifications
* Idempotency

---

# System Roles

BhuRaksha currently has three primary roles.

## Civilian

A Civilian can:

* Register an account
* Log in
* Create property verification cases
* Upload property documents
* View their own cases
* View document processing status
* View verification results
* Respond to proof requests
* Upload additional evidence
* View notifications
* View the final decision

A Civilian cannot access another Civilian's cases or documents.

---

## Area Officer

An Area Officer is assigned to a specific administrative area.

An Area Officer can:

* View cases within their assigned area
* Search cases
* Review documents
* Review OCR results
* Review extracted data
* Review registry validation
* Review GIS validation
* Review mismatches
* Review risk scores
* Request additional proof
* Review submitted proof
* Revalidate evidence
* Approve cases
* Reject cases

Area Officers cannot access cases outside their jurisdiction.

---

## Super Admin

The Super Admin has system-wide administrative privileges.

The Super Admin can:

* Manage areas
* Manage officers
* Assign officers to areas
* Manage users
* Search all cases
* View system statistics
* Monitor queues
* Monitor jobs
* View system health
* Perform administrative operations

Administrative operations are audited.

---

# Verification Workflow

The complete property verification workflow is:

```text
Civilian
   │
   ▼
Create Case
   │
   ▼
Upload Property Documents
   │
   ▼
Document Processing
   │
   ▼
DeepSeek OCR
   │
   │ Local Ollama
   ▼
OCR Output
   │
   ▼
Structured Field Extraction
   │
   ▼
Property / Parcel Profile
   │
   ├─────────────────────┐
   ▼                     ▼
Registry Validation    GIS/PostGIS Validation
   │                     │
   └──────────┬──────────┘
              ▼
       Mismatch Detection
              │
              ▼
        Risk Assessment
              │
              ▼
       Area Officer Review
              │
        ┌─────┴─────┐
        │           │
        ▼           ▼
  Request Proof   Decision
        │           │
        ▼           │
     Civilian       │
     Submission     │
        │           │
        ▼           │
    Revalidation    │
        │           │
        ▼           │
 Officer Re-review  │
        │           │
        └─────┬─────┘
              ▼
       Final Decision
         │         │
         ▼         ▼
      APPROVE    REJECT
         │         │
         └────┬────┘
              ▼
       Decision Snapshot
              │
       ┌──────┼──────┐
       ▼      ▼      ▼
     Audit  Outbox  Notification
```

---

# Architecture

The current development environment runs locally.

```text
                         ┌─────────────────────┐
                         │       CIVILIAN       │
                         └──────────┬──────────┘
                                    │
                                    ▼
                         ┌─────────────────────┐
                         │      FRONTEND       │
                         └──────────┬──────────┘
                                    │ HTTP
                                    ▼
                         ┌─────────────────────┐
                         │     BACKEND API     │
                         │       FastAPI       │
                         └──────────┬──────────┘
                                    │
            ┌───────────────────────┼───────────────────────┐
            │                       │                       │
            ▼                       ▼                       ▼
   ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
   │ PostgreSQL      │    │ Local Storage   │    │ Ollama          │
   │ + PostGIS       │    │                 │    │                 │
   │                 │    │ Property Docs   │    │ DeepSeek OCR    │
   └─────────────────┘    └─────────────────┘    └─────────────────┘
            │
            ▼
      GIS Validation
```

## Important

The current local development setup does not require:

* AWS S3
* Amazon RDS
* Cloud PostGIS
* Cloud OCR
* Cloud document storage

The database runs locally in Docker.

DeepSeek OCR runs locally through Ollama.

Documents are stored using the local storage backend.

---

# Technology Stack

## Backend

* Python
* FastAPI
* SQLAlchemy
* Psycopg
* Pydantic
* Pydantic Settings
* Alembic
* JWT authentication
* Pytest

## Database

* PostgreSQL 16
* PostGIS 3.4

## OCR

* Ollama
* DeepSeek OCR

## Storage

* Local filesystem storage

## Frontend

The frontend communicates with the FastAPI backend through the REST API.

Use the package manager and framework configuration included in the frontend project.

---

# Requirements

Install the following software.

## Required

* Git
* Python 3
* Docker
* Node.js
* npm/pnpm/yarn
* Ollama

Verify the installations:

```bash
git --version
python3 --version
docker --version
node --version
npm --version
ollama --version
```

---

# Project Structure

A typical repository structure is:

```text
BhuRaksha/
├── backend/
│   ├── app/
│   ├── alembic/
│   ├── tests/
│   ├── storage/
│   ├── .env
│   ├── .env.example
│   ├── .sops.yaml
│   ├── alembic.ini
│   └── pyproject.toml
│
├── frontend/
│   ├── src/
│   ├── public/
│   ├── package.json
│   └── ...
│
├── .gitignore
├── .env.enc
└── README.md
```

The exact frontend structure may vary depending on the frontend framework.

---

# Backend Setup

Move into the backend directory:

```bash
cd backend
```

---

## Create Virtual Environment

Linux/macOS:

```bash
python3 -m venv .venv
```

Activate it:

```bash
source .venv/bin/activate
```

You should see:

```text
(.venv)
```

in your terminal.

---

# Install Backend Dependencies

If the project uses `requirements.txt`:

```bash
pip install -r requirements.txt
```

If the project uses `pyproject.toml`:

```bash
pip install -e .
```

Install development dependencies as required by the project.

---

# PostgreSQL + PostGIS Setup

BhuRaksha uses a single Docker container containing:

```text
PostgreSQL
+
PostGIS
```

A separate PostgreSQL container is not required.

---

## Create PostGIS Container

Run:

```bash
docker run -d \
  --name property-postgis \
  -e POSTGRES_USER=property \
  -e POSTGRES_PASSWORD=property_password \
  -e POSTGRES_DB=property \
  -p 5432:5432 \
  -v property_postgis_data:/var/lib/postgresql/data \
  postgis/postgis:16-3.4
```

---

## Check Container

```bash
docker ps
```

The container should appear as:

```text
property-postgis
```

The port mapping should contain:

```text
0.0.0.0:5432->5432/tcp
```

---

## Check Database Logs

```bash
docker logs property-postgis
```

Wait for:

```text
database system is ready to accept connections
```

---

## Verify PostgreSQL + PostGIS

```bash
docker exec -it property-postgis \
  psql -U property -d property \
  -c "SELECT version(), PostGIS_Version();"
```

Both PostgreSQL and PostGIS versions should be returned.

---

# Starting PostgreSQL Later

After the container has already been created:

```bash
docker start property-postgis
```

Stop it:

```bash
docker stop property-postgis
```

Check:

```bash
docker ps
```

---

# Environment Configuration

Create the environment file:

```bash
cp .env.example .env
```

A local development configuration can look like:

```env
APP_NAME=BhuRaksha
APP_VERSION=0.1.0
ENVIRONMENT=development
DEBUG=true

API_V1_PREFIX=/api/v1

HOST=0.0.0.0
PORT=8000

LOG_LEVEL=INFO

ALLOWED_ORIGINS=["http://localhost:3000","http://localhost:5173"]

DATABASE_URL=postgresql+psycopg://property:property_password@localhost:5432/property

JWT_SECRET=CHANGE_THIS_TO_A_SECURE_RANDOM_SECRET
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7

INITIAL_ADMIN_EMAIL=admin@example.com
INITIAL_ADMIN_PASSWORD=CHANGE_THIS_PASSWORD

STORAGE_BACKEND=local
STORAGE_ROOT=./storage
MAX_UPLOAD_SIZE_MB=25

OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=deepseek-ocr
OLLAMA_TIMEOUT_SECONDS=300

OCR_MAX_RETRIES=2
OCR_MAX_CONCURRENCY=1
MAX_DOCUMENT_PAGES=100

RUN_OLLAMA_TESTS=true

EXTRACTION_MODEL=deepseek-ocr
EXTRACTION_TIMEOUT_SECONDS=300
EXTRACTION_MAX_RETRIES=2
EXTRACTION_UNCERTAIN_THRESHOLD=0.70

AREA_MATCH_TOLERANCE_PERCENT=1.0
GIS_AREA_TOLERANCE_PERCENT=2.0
```

Do not commit the real `.env`.

---

# Generate a Secure JWT Secret

Generate a strong development secret:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Set:

```env
JWT_SECRET=<generated-secret>
```

Do not use the placeholder value in production.

---

# Database Migrations

After PostgreSQL/PostGIS is running:

```bash
alembic upgrade head
```

Check the current migration:

```bash
alembic current
```

The database must be migrated before normal application use.

---

# Local Document Storage

BhuRaksha currently uses local filesystem storage:

```env
STORAGE_BACKEND=local
STORAGE_ROOT=./storage
```

Create the directory if necessary:

```bash
mkdir -p storage
```

Uploaded documents should not be committed to Git.

Add:

```gitignore
storage/
```

to `.gitignore`.

---

# Ollama + DeepSeek OCR Setup

BhuRaksha uses DeepSeek OCR running locally through Ollama.

The architecture is:

```text
Backend
   │
   ▼
Ollama
   │
   ▼
DeepSeek OCR
```

No cloud OCR service is required.

---

# Verify Ollama

```bash
ollama --version
```

Check installed models:

```bash
ollama list
```

The configured model is:

```env
OLLAMA_MODEL=deepseek-ocr
```

---

# Start Ollama

If Ollama is not already running:

```bash
ollama serve
```

The backend expects:

```text
http://localhost:11434
```

Verify:

```bash
curl http://localhost:11434
```

---

# Test DeepSeek OCR

Run:

```bash
RUN_OLLAMA_TESTS=true pytest -v tests/ocr/test_real_ollama_integration.py
```

Expected:

```text
1 passed
```

This performs the real local Ollama/DeepSeek OCR integration test.

---

# Test Environment Configuration

Verify that Pydantic can load the environment:

```bash
python -c "from app.core.config import settings; print(settings.ALLOWED_ORIGINS)"
```

Expected:

```text
['http://localhost:3000', 'http://localhost:5173']
```

---

# Starting the Backend

From the backend directory:

```bash
source .venv/bin/activate
```

Start FastAPI:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

The backend runs at:

```text
http://localhost:8000
```

---

# Backend API

API base URL:

```text
http://localhost:8000/api/v1
```

Swagger documentation:

```text
http://localhost:8000/docs
```

OpenAPI specification:

```text
http://localhost:8000/openapi.json
```

---

# Backend Health Check

Run:

```bash
curl http://localhost:8000/health
```

The application should return a successful health response.

---

# Frontend Setup

Open a new terminal.

Move into the frontend directory:

```bash
cd frontend
```

Install dependencies.

For npm:

```bash
npm install
```

For pnpm:

```bash
pnpm install
```

For yarn:

```bash
yarn install
```

Use the package manager configured by the repository.

---

# Frontend Environment

Configure the frontend to communicate with the backend.

For a Vite-style application, this may be:

```env
VITE_API_URL=http://localhost:8000/api/v1
```

For a Next.js-style application, this may be:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
```

Use the environment variable expected by the actual frontend implementation.

---

# Starting the Frontend

For npm:

```bash
npm run dev
```

Typical development URLs are:

```text
http://localhost:3000
```

or:

```text
http://localhost:5173
```

Use the URL printed by the frontend development server.

---

# Running the Complete Application

The recommended local startup order is:

```text
1. PostgreSQL + PostGIS
2. Database migrations
3. Ollama
4. DeepSeek OCR
5. Backend API
6. Background workers
7. Frontend
```

---

## Terminal 1 — PostgreSQL + PostGIS

```bash
docker start property-postgis
```

---

## Terminal 2 — Ollama

```bash
ollama serve
```

If Ollama is already running as a system service, do not start another instance.

---

## Terminal 3 — Backend

```bash
cd backend
source .venv/bin/activate

alembic upgrade head

uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

---

## Terminal 4 — Frontend

```bash
cd frontend
npm run dev
```

---

# Background Workers

If the application defines separate worker processes, start the worker processes according to the project's worker entry points.

Workers are responsible for asynchronous processing such as:

* Document processing
* OCR jobs
* Validation jobs
* Outbox events
* Notifications

Use the worker entry points provided by the backend implementation.

---

# Testing

Activate the backend environment:

```bash
cd backend
source .venv/bin/activate
```

Run the complete test suite:

```bash
RUN_OLLAMA_TESTS=true pytest -v tests/
```

---

# Test Result

The backend has been fully verified.

Current verified result:

```text
Total Tests: 161
Passed: 161
Failed: 0
Skipped: 0
Pass Rate: 100%
```

The suite includes the real local DeepSeek OCR integration.

---

# OCR Tests

Run all OCR tests:

```bash
RUN_OLLAMA_TESTS=true pytest -v tests/ocr/
```

Run the real Ollama test:

```bash
RUN_OLLAMA_TESTS=true \
pytest -v tests/ocr/test_real_ollama_integration.py
```

---

# End-to-End Test

Run the complete lifecycle:

```bash
RUN_OLLAMA_TESTS=true \
pytest -v tests/e2e/test_complete_lifecycle.py
```

The E2E flow covers:

```text
Civilian Submission
        ↓
Document Processing
        ↓
DeepSeek OCR
        ↓
Extraction
        ↓
Registry Validation
        ↓
GIS Validation
        ↓
Risk Assessment
        ↓
Officer Review
        ↓
Proof Request
        ↓
Proof Submission
        ↓
Revalidation
        ↓
Final Decision
```

---

# Migration Tests

Run:

```bash
pytest -v tests/database/test_migrations.py
```

The migration tests verify:

* Upgrade
* Downgrade
* Re-upgrade
* Database migration integrity

---

# Authentication Tests

Run:

```bash
pytest -v tests/auth/
```

Authentication testing covers:

* Registration
* Login
* Logout
* Access tokens
* Refresh tokens
* Current user
* Security
* Duplicate registration handling

---

# Security Tests

The security suite verifies:

* Authentication
* Authorization
* RBAC
* Area isolation
* SQL injection protection
* Path traversal protection
* Upload validation
* Rate limiting
* Security headers
* Correlation IDs
* Concurrency
* Terminal-state immutability

---

# Authentication and RBAC

BhuRaksha uses JWT-based authentication.

Configuration:

```env
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7
```

The authorization hierarchy is:

```text
Authentication
      ↓
Role-Based Access Control
      ↓
Ownership / Jurisdiction
      ↓
Resource Authorization
```

---

# Civilian Authorization

A civilian can access only their own resources.

Conceptually:

```text
case.owner_id == current_user.id
```

Client-provided IDs must never override server-side authorization.

---

# Area Officer Authorization

An Area Officer can access only cases belonging to their assigned area.

Conceptually:

```text
case.area_id == officer.assigned_area_id
```

This prevents cross-area access.

---

# Super Admin Authorization

Super Admin users have system-wide administrative access.

Administrative operations remain auditable.

---

# GIS and PostGIS

PostGIS is used for spatial validation.

The GIS subsystem supports:

* Parcel validation
* Spatial rules
* Area calculations
* Geometry validation
* GIS mismatch detection
* Spatial imports
* Property mapping

Verify PostGIS:

```bash
docker exec -it property-postgis \
  psql -U property -d property \
  -c "SELECT PostGIS_Version();"
```

---

# Property and Parcel Validation

The system builds a property/parcel profile from available evidence.

Validation can combine:

```text
Document Data
     +
Registry Data
     +
GIS Data
     +
Evidence
     ↓
Property Profile
```

The system then evaluates inconsistencies.

---

# Mismatch and Risk Engine

The mismatch engine identifies conflicts between sources.

Examples include:

* Name mismatch
* Area mismatch
* Parcel mismatch
* Registry mismatch
* GIS mismatch
* Document inconsistency

Risk scoring then evaluates the severity of detected conflicts.

Configuration:

```env
AREA_MATCH_TOLERANCE_PERCENT=1.0
GIS_AREA_TOLERANCE_PERCENT=2.0
```

---

# OCR and Document Processing

The document pipeline is:

```text
Uploaded Document
       ↓
File Validation
       ↓
Preprocessing
       ↓
DeepSeek OCR
       ↓
OCR Result
       ↓
Structured Extraction
       ↓
Schema Validation
       ↓
Normalization
       ↓
Verification
```

OCR failures are handled explicitly and do not automatically result in property rejection.

---

# DeepSeek OCR

DeepSeek OCR runs locally.

Configuration:

```env
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=deepseek-ocr
OLLAMA_TIMEOUT_SECONDS=300
```

OCR retry configuration:

```env
OCR_MAX_RETRIES=2
OCR_MAX_CONCURRENCY=1
MAX_DOCUMENT_PAGES=100
```

---

# Document Upload Limits

Current configuration:

```env
MAX_UPLOAD_SIZE_MB=25
MAX_DOCUMENT_PAGES=100
```

Uploaded files are validated before processing.

The system protects against:

* Invalid file types
* Invalid file signatures
* Oversized uploads
* Path traversal
* Unauthorized access

---

# Proof and Revalidation Workflow

When an Area Officer needs additional evidence:

```text
Officer
   ↓
Proof Request
   ↓
Civilian
   ↓
Proof Submission
   ↓
Document Processing
   ↓
DeepSeek OCR
   ↓
Extraction
   ↓
Revalidation
   ↓
Officer Review
```

The original review state is preserved through the audit and decision history.

---

# Final Decision

A case can eventually reach a terminal state such as:

```text
APPROVED
```

or:

```text
REJECTED
```

Terminal states are protected against unauthorized modification.

Final decisions generate immutable snapshots for historical integrity.

---

# Audit Trail

Important system actions are audited.

Examples:

* Case creation
* Document upload
* OCR processing
* Extraction
* Validation
* Risk calculation
* Review start
* Review decision
* Proof request
* Proof submission
* Revalidation
* Final decision
* Administrative operations

The audit trail provides traceability throughout the verification lifecycle.

---

# Notifications and Outbox

BhuRaksha uses an outbox-based event architecture.

```text
Business Operation
       ↓
Database Transaction
       ↓
Outbox Event
       ↓
Outbox Worker
       ↓
Notification
```

This allows business operations and notification events to remain reliable and auditable.

---

# Idempotency

Critical operations support idempotency to prevent duplicate effects.

This is especially important for:

* Notifications
* Outbox events
* Final decisions
* Processing jobs
* Repeated requests

---

# Local Storage

The current storage backend is:

```env
STORAGE_BACKEND=local
```

Storage location:

```env
STORAGE_ROOT=./storage
```

The storage directory should not be committed.

Add to `.gitignore`:

```gitignore
storage/
```

---

# SOPS and Encrypted Environment Files

BhuRaksha can use SOPS with age to keep environment secrets encrypted while allowing the encrypted configuration to be committed to Git.

Recommended files:

```text
.env.example       → Commit
.env.enc           → Commit
.sops.yaml         → Commit
.env               → Do not commit
age private key    → Do not commit
```

The default age key is typically stored at:

```text
~/.config/sops/age/keys.txt
```

The private age key must never be committed.

---

# SOPS Configuration

Example `.sops.yaml`:

```yaml
creation_rules:
  - path_regex: '.*\.enc$'
    age: age1YOUR_PUBLIC_KEY_HERE
```

Replace:

```text
age1YOUR_PUBLIC_KEY_HERE
```

with the public age recipient.

Get the public key:

```bash
grep '^# public key:' ~/.config/sops/age/keys.txt
```

Never share or commit the private:

```text
AGE-SECRET-KEY-...
```

value.

---

# Encrypt the Environment

From the project directory:

```bash
sops --encrypt .env > .env.enc
```

If SOPS does not automatically detect `.sops.yaml`:

```bash
sops --config .sops.yaml --encrypt .env > .env.enc
```

---

# Decrypt the Environment

```bash
sops --decrypt .env.enc > .env
```

Or:

```bash
sops --config .sops.yaml --decrypt .env.enc > .env
```

---

# Git Secret Protection

The real `.env` should be ignored:

```gitignore
.env
.env.*
!.env.example
!.env.enc

storage/
.venv/
__pycache__/
.pytest_cache/
*.log
```

Do not commit:

```text
.env
AGE-SECRET-KEY-*
~/.config/sops/age/keys.txt
```

---

# Useful Docker Commands

List running containers:

```bash
docker ps
```

List all containers:

```bash
docker ps -a
```

Start PostgreSQL/PostGIS:

```bash
docker start property-postgis
```

Stop PostgreSQL/PostGIS:

```bash
docker stop property-postgis
```

View logs:

```bash
docker logs property-postgis
```

Follow logs:

```bash
docker logs -f property-postgis
```

Open PostgreSQL shell:

```bash
docker exec -it property-postgis \
  psql -U property -d property
```

---

# Troubleshooting

## PostgreSQL Connection Refused

Error:

```text
connection to server at "127.0.0.1", port 5432 failed:
Connection refused
```

Check:

```bash
docker ps
```

Make sure:

```text
property-postgis
```

is running.

The port mapping should contain:

```text
0.0.0.0:5432->5432/tcp
```

Start the container:

```bash
docker start property-postgis
```

---

# PostgreSQL Container Running but Port Missing

If:

```bash
docker ps
```

shows an empty `PORTS` column, the container was created without port publishing.

Remove the container:

```bash
docker stop property-postgis
docker rm property-postgis
```

If a named volume was used, database data remains in the volume.

Recreate:

```bash
docker run -d \
  --name property-postgis \
  -e POSTGRES_USER=property \
  -e POSTGRES_PASSWORD=property_password \
  -e POSTGRES_DB=property \
  -p 5432:5432 \
  -v property_postgis_data:/var/lib/postgresql/data \
  postgis/postgis:16-3.4
```

---

# Database Tables Do Not Exist

If an error contains:

```text
relation "users" does not exist
```

run:

```bash
alembic upgrade head
```

Then verify:

```bash
docker exec -it property-postgis \
  psql -U property -d property \
  -c "\dt"
```

---

# PostGIS Unavailable

Run:

```bash
docker exec -it property-postgis \
  psql -U property -d property \
  -c "SELECT PostGIS_Version();"
```

If the command succeeds, PostGIS is available.

---

# Ollama Unavailable

Check:

```bash
ollama list
```

Check the Ollama endpoint:

```bash
curl http://localhost:11434
```

Start Ollama if required:

```bash
ollama serve
```

---

# DeepSeek OCR Test Is Skipped

Run:

```bash
RUN_OLLAMA_TESTS=true \
pytest -v tests/ocr/test_real_ollama_integration.py
```

The expected result is:

```text
1 passed
```

---

# ALLOWED_ORIGINS Configuration Error

If Pydantic reports:

```text
SettingsError: error parsing value for field "ALLOWED_ORIGINS"
```

use JSON-array syntax:

```env
ALLOWED_ORIGINS=["http://localhost:3000","http://localhost:5173"]
```

Do not use:

```env
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:5173
```

---

# Migration Event Loop Errors

The migration test uses Alembic against the real database.

If you see:

```text
RuntimeError: asyncio.run() cannot be called from a running event loop
```

inspect the Alembic environment and migration test rather than skipping the test.

The migration test must continue to verify:

```text
upgrade
   ↓
downgrade
   ↓
upgrade
```

against the real PostgreSQL/PostGIS database.

Do not disable or skip the migration test to hide this error.

---

# Port Configuration

## Backend

```text
8000
```

## PostgreSQL/PostGIS

```text
5432
```

## Ollama

```text
11434
```

## Frontend

Typically:

```text
3000
```

or:

```text
5173
```

depending on the frontend framework.

---

# Local Service Summary

| Service      | Host                 |        Port |
| ------------ | -------------------- | ----------: |
| Frontend     | localhost            | 3000 / 5173 |
| Backend      | localhost            |        8000 |
| PostgreSQL   | localhost            |        5432 |
| PostGIS      | PostgreSQL extension |        5432 |
| Ollama       | localhost            |       11434 |
| DeepSeek OCR | Ollama               |       11434 |

---

# Development Workflow

When modifying the backend:

1. Start PostgreSQL/PostGIS.
2. Start Ollama.
3. Activate the Python virtual environment.
4. Run migrations if the database schema changed.
5. Make the code change.
6. Add/update tests.
7. Run the relevant test group.
8. Run the full test suite.
9. Confirm that no regression was introduced.

Full test command:

```bash
RUN_OLLAMA_TESTS=true pytest -v tests/
```

The goal is:

```text
161 passed
0 failed
0 skipped
```

---

# Recommended Development Startup

For daily development:

### 1. Database

```bash
docker start property-postgis
```

### 2. Ollama

Ensure Ollama is running:

```bash
ollama list
```

### 3. Backend

```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 4. Frontend

```bash
cd frontend
npm run dev
```

---

# Clean Development Setup

For a new machine:

```bash
git clone <REPOSITORY_URL>
cd BhuRaksha
```

Start PostgreSQL/PostGIS:

```bash
docker run -d \
  --name property-postgis \
  -e POSTGRES_USER=property \
  -e POSTGRES_PASSWORD=property_password \
  -e POSTGRES_DB=property \
  -p 5432:5432 \
  -v property_postgis_data:/var/lib/postgresql/data \
  postgis/postgis:16-3.4
```

Backend:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

Create environment:

```bash
cp .env.example .env
```

Run migrations:

```bash
alembic upgrade head
```

Start Ollama:

```bash
ollama serve
```

Start backend:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Open another terminal for the frontend:

```bash
cd frontend
npm install
npm run dev
```

---

# Production Considerations

The current configuration is intended for local development.

Before production deployment:

* Replace development JWT secrets
* Replace default admin credentials
* Disable debug mode
* Configure secure CORS
* Use HTTPS
* Secure PostgreSQL
* Use production-grade database credentials
* Use proper secret management
* Protect document storage
* Configure database backups
* Configure monitoring
* Configure centralized logging
* Configure worker supervision
* Configure resource limits
* Configure firewall rules
* Review rate limits
* Review upload limits
* Review authentication policies
* Secure Ollama/DeepSeek OCR infrastructure
* Ensure production data is not stored in development volumes
* Review all administrative permissions

---

# Security Principles

BhuRaksha follows these core security principles:

```text
Never trust client-provided authorization data.

Authenticate first.

Authorize every resource access.

Enforce Area Officer jurisdiction server-side.

Keep civilian data isolated.

Validate uploaded documents.

Prevent path traversal.

Protect secrets.

Audit sensitive operations.

Protect terminal states.

Make critical operations idempotent.
```

---

# Test Property Documents

Automated tests may use fixture documents such as:

```text
test_property.pdf
```

This represents an initial property document.

Proof workflow tests may use:

```text
test_proof.pdf
```

This represents additional evidence submitted by a civilian after an Area Officer requests proof.

These are test fixtures and should not contain real citizen data.

---

# API Development

The API is versioned under:

```text
/api/v1
```

Example:

```text
http://localhost:8000/api/v1
```

Interactive API documentation:

```text
http://localhost:8000/docs
```

Use the Swagger/OpenAPI interface during development to inspect available endpoints and request/response schemas.

---

# Project Completion Status

The BhuRaksha backend has completed the full development and verification cycle.

Verified areas include:

```text
✓ Backend Architecture
✓ PostgreSQL
✓ PostGIS
✓ Authentication
✓ User Management
✓ RBAC
✓ Area Isolation
✓ Case Lifecycle
✓ Case Numbering
✓ Document Upload
✓ Local Storage
✓ Document Authorization
✓ DeepSeek OCR
✓ Ollama Integration
✓ OCR Preprocessing
✓ OCR Error Handling
✓ Structured Extraction
✓ Evidence
✓ Property Profile
✓ Registry Validation
✓ Name Matching
✓ GIS Validation
✓ Spatial Rules
✓ Mismatch Engine
✓ Risk Engine
✓ Officer Review
✓ Review Locking
✓ Proof Requests
✓ Proof Submission
✓ Revalidation
✓ Final Decisions
✓ Decision Snapshots
✓ Terminal State Protection
✓ Audit
✓ Notifications
✓ Outbox
✓ Idempotency
✓ Admin Dashboard
✓ Admin Operations
✓ Queue Monitoring
✓ System Health
✓ Security Hardening
✓ Concurrency Handling
✓ Full E2E Lifecycle
✓ Database Migrations
```

---

# Final Verified Test Result

```text
╔══════════════════════════════════════════╗
║          BHURAKSHA TEST SUITE            ║
╠══════════════════════════════════════════╣
║ Total Tests       161                    ║
║ Passed            161                    ║
║ Failed              0                    ║
║ Skipped             0                    ║
║ Pass Rate         100%                   ║
║ DeepSeek OCR      VERIFIED               ║
║ PostGIS           VERIFIED               ║
║ Migrations        VERIFIED               ║
╚══════════════════════════════════════════╝
```

---

# BhuRaksha Local Architecture

```text
                         BHURAKSHA
                             │
             ┌───────────────┴───────────────┐
             │                               │
             ▼                               ▼
         CIVILIAN                       AREA OFFICER
             │                               │
             └───────────────┬───────────────┘
                             │
                             ▼
                       FRONTEND
                             │
                             ▼
                       FASTAPI API
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
        ▼                    ▼                    ▼
 PostgreSQL +          Local Document          Ollama
    PostGIS               Storage                │
        │                                         ▼
        │                                  DeepSeek OCR
        │                                         │
        └────────────────┬────────────────────────┘
                         ▼
                PROPERTY VERIFICATION
                         │
             ┌───────────┼───────────┐
             ▼           ▼           ▼
          Registry      GIS         Risk
          Matching   Validation    Engine
             │           │           │
             └───────────┼───────────┘
                         ▼
                  AREA OFFICER
                      REVIEW
                         │
                 ┌───────┴───────┐
                 ▼               ▼
            PROOF CYCLE       DECISION
                 │               │
                 ▼               ▼
            REVALIDATION     SNAPSHOT
                                 │
                    ┌────────────┼────────────┐
                    ▼            ▼            ▼
                  AUDIT        OUTBOX     NOTIFICATION
```

---

# BhuRaksha

**Secure Property Verification Through Documents, Registry Data, GIS, OCR, and Human Review.**

