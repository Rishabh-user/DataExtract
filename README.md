# Universal Data Extraction Platform

A production-grade platform built with FastAPI that extracts structured data from multiple document types and exposes it via REST APIs. Supports PDF, Excel, Word, Email, CSV, PowerPoint, and Images (OCR).

---

## Table of Contents

- [Architecture](#architecture)
- [Project Structure](#project-structure)
- [Prerequisites](#prerequisites)
- [Getting Started](#getting-started)
  - [1. Clone the Repository](#1-clone-the-repository)
  - [2. Environment Configuration](#2-environment-configuration)
  - [3. Option A — Docker (Recommended)](#3-option-a--docker-recommended)
  - [4. Option B — Local Development](#4-option-b--local-development)
- [API Reference](#api-reference)
- [Authentication](#authentication)
- [Supported File Formats](#supported-file-formats)
- [Database Schema](#database-schema)
- [Frontend UI](#frontend-ui)
- [Running Tests](#running-tests)
- [Troubleshooting](#troubleshooting)

---

## Architecture

```
┌──────────────┐     ┌──────────────┐     ┌──────────────────┐
│   Frontend   │────>│  FastAPI App  │────>│   PostgreSQL 16  │
│  (Jinja2 UI) │     │  (Uvicorn)   │     │  (metadata store)│
└──────────────┘     │  Port 8000   │     │  Port 5432       │
                     │              │────>│  Elasticsearch 8 │
                     │              │     │  (full-text search│
                     └──────────────┘     │  Port 9200)      │
                                          └──────────────────┘
```

- **FastAPI** — async web framework serving REST APIs and frontend templates
- **PostgreSQL** — stores document metadata, extracted content, and API keys
- **Elasticsearch** — powers full-text search with highlighting across all extracted content
- **Extraction Engine** — modular extractors for each file type, returning structured JSON

---

## Project Structure

```
data-extraction/
├── app/
│   ├── api/
│   │   ├── routes.py              # API endpoint definitions
│   │   └── schemas.py             # Pydantic request/response models
│   ├── core/
│   │   ├── config.py              # Environment-driven settings
│   │   ├── exceptions.py          # Custom exception classes
│   │   └── logging.py             # Centralized logging setup
│   ├── database/
│   │   ├── elasticsearch.py       # ES client, indexing, search
│   │   ├── models.py              # SQLAlchemy ORM models
│   │   └── session.py             # Async DB session factory
│   ├── extraction/
│   │   ├── base.py                # BaseExtractor ABC
│   │   ├── pdf_extractor.py       # pdfplumber + PyMuPDF + camelot
│   │   ├── excel_extractor.py     # pandas + openpyxl
│   │   ├── doc_extractor.py       # python-docx + docx2txt
│   │   ├── email_extractor.py     # stdlib email + extract-msg
│   │   ├── csv_extractor.py       # pandas with encoding detection
│   │   ├── ppt_extractor.py       # python-pptx
│   │   ├── image_extractor.py     # OpenCV + pytesseract OCR
│   │   ├── video_extractor.py     # Future placeholder
│   │   └── registry.py            # Extension → extractor mapping
│   ├── security/
│   │   └── auth.py                # API key generation & validation
│   ├── services/
│   │   └── extraction_service.py  # Upload, extract, persist, index
│   └── main.py                    # FastAPI app entry point
├── frontend/
│   ├── templates/                 # Jinja2 HTML (upload, view, filter)
│   └── static/                    # CSS and JavaScript
├── tests/                         # Unit and integration tests
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── pyproject.toml
├── alembic.ini
├── .env.example
├── .gitignore
└── .dockerignore
```

---

## Prerequisites

| Requirement          | Version   | Notes                                    |
|----------------------|-----------|------------------------------------------|
| Python               | >= 3.11   | 3.12 recommended                         |
| Docker & Docker Compose | Latest | Required for Option A                    |
| PostgreSQL           | 16+       | Required for Option B (if running locally)|
| Elasticsearch        | 8.x       | Required for Option B (if running locally)|
| Tesseract OCR        | 4.x / 5.x| Required only for image extraction        |

---

## Getting Started

### 1. Clone the Repository

```bash
git clone <repository-url>
cd data-extraction
```

### 2. Environment Configuration

Copy the example env file and edit as needed:

```bash
cp .env.example .env
```

Key variables in `.env`:

```env
# Application
APP_NAME=Universal Data Extraction Platform
DEBUG=false
LOG_LEVEL=INFO

# Server
HOST=0.0.0.0
PORT=8000

# PostgreSQL
POSTGRES_HOST=postgres          # Use "localhost" for local dev
POSTGRES_PORT=5432
POSTGRES_USER=extraction_user
POSTGRES_PASSWORD=changeme      # Change in production!
POSTGRES_DB=extraction_db

# Elasticsearch
ELASTICSEARCH_HOST=elasticsearch  # Use "localhost" for local dev
ELASTICSEARCH_PORT=9200
ELASTICSEARCH_SCHEME=http
ELASTICSEARCH_INDEX=extracted_documents

# File Storage
UPLOAD_DIR=uploads
MAX_FILE_SIZE_MB=100

# OCR (uncomment if tesseract is not on PATH)
# TESSERACT_CMD=/usr/bin/tesseract

# Processing
MAX_WORKERS=4
EXTRACTION_TIMEOUT_SECONDS=300
```

### 3. Option A — Docker (Recommended)

This starts the FastAPI app, PostgreSQL, and Elasticsearch in one command:

```bash
docker compose up --build
```

The services will be available at:

| Service         | URL                          |
|-----------------|------------------------------|
| FastAPI App     | http://localhost:8000        |
| API Docs (Swagger) | http://localhost:8000/docs |
| PostgreSQL      | localhost:5432               |
| Elasticsearch   | http://localhost:9200        |

To run in the background:

```bash
docker compose up --build -d
```

To stop:

```bash
docker compose down
```

To stop and remove all data volumes:

```bash
docker compose down -v
```

### 4. Option B — Local Development

#### Step 1: Start PostgreSQL and Elasticsearch

You can either install them locally or use Docker for just the databases:

```bash
docker compose up postgres elasticsearch -d
```

#### Step 2: Update `.env` for local dev

```env
POSTGRES_HOST=localhost
ELASTICSEARCH_HOST=localhost
```

#### Step 3: Create a Python virtual environment

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate
```

#### Step 4: Install dependencies

```bash
pip install -r requirements.txt
```

#### Step 5: Install Tesseract OCR (for image extraction)

- **Windows**: Download installer from https://github.com/UB-Mannheim/tesseract/wiki and add to PATH, or set `TESSERACT_CMD` in `.env`
- **macOS**: `brew install tesseract`
- **Ubuntu/Debian**: `sudo apt install tesseract-ocr`

#### Step 6: Start the dev server

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

The app auto-creates database tables on startup.

Open http://localhost:8000 to access the UI, or http://localhost:8000/docs for the Swagger API explorer.

---

## API Reference

All API endpoints require an `x-api-key` header (except key generation).

### Generate an API Key

```bash
curl -X POST http://localhost:8000/api/auth/generate-key \
  -H "Content-Type: application/json" \
  -d '{"project_name": "my-app"}'
```

Response:

```json
{
  "id": 1,
  "project_name": "my-app",
  "api_key": "a1b2c3d4...",
  "permissions": {"read": true, "write": true, "search": true},
  "created_at": "2026-03-17T10:00:00",
  "message": "API key generated successfully. Store it securely — it cannot be retrieved again."
}
```

### Upload a Document

```bash
curl -X POST http://localhost:8000/api/upload \
  -H "x-api-key: YOUR_API_KEY" \
  -F "file=@document.pdf" \
  -F "source=client-portal"
```

### Get Extracted Content

```bash
curl http://localhost:8000/api/document/1 \
  -H "x-api-key: YOUR_API_KEY"
```

### Full-Text Search

```bash
curl "http://localhost:8000/api/search?q=invoice&file_type=.pdf&page=1&size=20" \
  -H "x-api-key: YOUR_API_KEY"
```

### Filter Documents

```bash
curl "http://localhost:8000/api/filter?file_type=.pdf&source=client-portal&date_from=2026-01-01" \
  -H "x-api-key: YOUR_API_KEY"
```

---

## Authentication

All endpoints (except `/api/auth/generate-key`) require API key authentication.

1. Generate a key via `POST /api/auth/generate-key`
2. Include it in every request as a header:

```
x-api-key: your-api-key-here
```

Invalid or missing keys return `401 Unauthorized`.

---

## Supported File Formats

| Format     | Extensions             | Library                              |
|------------|------------------------|--------------------------------------|
| PDF        | `.pdf`                 | pdfplumber, PyMuPDF, camelot         |
| Excel      | `.xlsx`, `.xls`        | pandas, openpyxl, xlrd               |
| Word       | `.docx`, `.doc`        | python-docx, docx2txt                |
| Email      | `.eml`, `.msg`         | stdlib email, extract-msg            |
| CSV        | `.csv`                 | pandas                               |
| PowerPoint | `.pptx`, `.ppt`        | python-pptx                          |
| Image (OCR)| `.png`, `.jpg`, `.jpeg`, `.tiff`, `.bmp` | pytesseract, OpenCV, Pillow |
| Video      | `.mp4`, `.avi`, `.mov` | Placeholder (future support)         |

---

## Database Schema

### `documents`

| Column          | Type         | Description                |
|-----------------|--------------|----------------------------|
| id              | Integer (PK) | Auto-increment primary key |
| file_name       | String(500)  | Original file name         |
| file_type       | String(50)   | File extension (e.g. .pdf) |
| source          | String(255)  | Optional source label      |
| upload_date     | DateTime     | When the file was uploaded |
| file_path       | String(1000) | Path on disk               |
| file_size_bytes | Integer      | File size in bytes         |
| status          | Enum         | pending / processing / completed / failed |

### `extracted_data`

| Column      | Type         | Description                     |
|-------------|--------------|---------------------------------|
| id          | Integer (PK) | Auto-increment primary key      |
| document_id | Integer (FK) | References documents.id         |
| page_number | Integer      | Page or section number          |
| content     | Text         | Extracted text content          |
| metadata    | JSONB        | Structured metadata (tables, etc.) |
| created_at  | DateTime     | Extraction timestamp            |

### `api_keys`

| Column       | Type         | Description                    |
|--------------|--------------|--------------------------------|
| id           | Integer (PK) | Auto-increment primary key    |
| project_name | String(255)  | Project this key belongs to   |
| api_key      | String(64)   | The API key (unique, indexed) |
| permissions  | JSONB        | e.g. {read, write, search}    |
| created_at   | DateTime     | Key creation timestamp        |
| status       | Enum         | active / revoked              |

---

## Frontend UI

The platform includes three built-in UI screens accessible via browser:

| Page            | URL                          | Description                     |
|-----------------|------------------------------|---------------------------------|
| Upload Document | http://localhost:8000/       | Drag-and-drop file upload       |
| View Extracted  | http://localhost:8000/view/1 | View extracted content by doc ID|
| Filter & Search | http://localhost:8000/documents | Filter by type, source, date; full-text search |

---

## Running Tests

```bash
# Install test dependencies
pip install pytest pytest-asyncio

# Run all tests
pytest

# Run with verbose output
pytest -v

# Run a specific test file
pytest tests/test_extractors.py
```

---

## Troubleshooting

### Elasticsearch won't start (Docker)

Elasticsearch 8.x needs `vm.max_map_count >= 262144`. On Linux/WSL:

```bash
sudo sysctl -w vm.max_map_count=262144
```

### Tesseract not found

Set the path explicitly in `.env`:

```env
TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe
```

### Port already in use

Change the port in `.env` and restart:

```env
PORT=8001
```

### Database connection refused

Ensure PostgreSQL is running and the `.env` host is correct:
- Docker: `POSTGRES_HOST=postgres`
- Local: `POSTGRES_HOST=localhost`

### Camelot table extraction fails

Camelot requires Ghostscript. Install it:
- **Windows**: https://www.ghostscript.com/releases/gsdnld.html
- **macOS**: `brew install ghostscript`
- **Ubuntu**: `sudo apt install ghostscript`
