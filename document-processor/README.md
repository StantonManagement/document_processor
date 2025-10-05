# Document Processing & Generation Service

A FastAPI-based service for processing documents (PDFs, images, DOCX) with OCR capabilities, text extraction, intelligent parsing, and template-based document generation.

## 📑 Table of Contents

- [Features](#-features)
- [Documentation](#-documentation)
- [Quick Start](#-quick-start)
- [Docker Quick Start](#-docker-quick-start)
- [Quick Testing Examples](#-quick-testing-examples)
- [API Endpoints](#-api-endpoints)
- [Workflows](#-workflows)
- [Configuration](#configuration)
- [Architecture](#architecture-overview)
- [Testing & Coverage](#testing--coverage)
- [Troubleshooting](#troubleshooting)

## ✨ Features

### Document Processing

- 📄 **Multi-format Support**: PDF, PNG, JPG, DOCX
- 🔍 **OCR Integration**: Tesseract-based text extraction
- 📝 **Text Extraction**: Plain text, JSON, and Markdown formats
- 🧾 **Intelligent Parsing**: Invoice, receipt, and contract parsing

### Document Generation

- 📋 **Template Management**: Create, update, and version templates
- 🎨 **Jinja2 Rendering**: Dynamic template rendering with custom filters
- 📑 **PDF Generation**: HTML to PDF conversion (WeasyPrint)
- 🏛️ **State Compliance**: State-specific legal document templates (CA, NY, TX, FL, IL)
- ✍️ **E-Signature Integration**: PDFfiller integration for signature workflows
- 🔄 **Document Regeneration**: Update and regenerate documents with new data

### Additional Features

- 🔐 **Rate Limiting**: Built-in request throttling
- 📊 **Health Checks**: Comprehensive health monitoring
- 🧪 **Comprehensive Testing**: 47 tests with 100% pass rate
- 📚 **API Documentation**: Interactive Swagger/OpenAPI docs
- 🐳 **Docker Support**: Ready-to-deploy containerization

## 📚 Documentation

- **[API Documentation](docs/API_DOCUMENTATION.md)** - Complete API reference with examples
- **[Quick Start Guide](docs/QUICK_START.md)** - Get started quickly
- **[Implementation Summary](docs/IMPLEMENTATION_SUMMARY.md)** - Detailed implementation overview
- **[Compliance Checklist](docs/COMPLIANCE_CHECKLIST.md)** - Specification compliance verification

---

## 🚀 Quick Start

### Prerequisites

- **Python 3.10+** (3.11+ recommended)
- **Optional**: Tesseract OCR (for document processing OCR). If not installed, use Docker which bundles it.
- **Optional**: WeasyPrint system libraries (for PDF generation on Linux/Mac). On Windows, use Docker or HTML output format.

### Installation

#### Option 1: Using uv (Recommended)

```bash
# Create virtual environment
uv venv .venv

# Activate virtual environment
# On Windows (Git Bash)
source .venv/Scripts/activate
# On Windows (cmd/PowerShell)
.venv\Scripts\activate
# On Linux/Mac
source .venv/bin/activate

# Install dependencies
uv pip install -r requirements.txt
```

#### Option 2: Using standard venv + pip

```bash
# Create virtual environment
python -m venv .venv

# Activate virtual environment
# On Windows (Git Bash)
source .venv/Scripts/activate
# On Windows (cmd/PowerShell)
.venv\Scripts\activate
# On Linux/Mac
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Running the Service

#### Start the API server

```bash
# From the document-processor directory
uvicorn app.main:app --reload
```

The service will be available at:

- **API**: http://localhost:8000
- **Interactive API Docs**: http://localhost:8000/docs
- **Alternative Docs**: http://localhost:8000/redoc

#### Health Check

```bash
curl http://localhost:8000/health
# Expected: {"status":"ok", ...}
```

### Running Tests

#### Run all tests

```bash
# From the document-processor directory
python -m pytest -v
```

#### Run specific test suites

```bash
# Template service tests
python -m pytest tests/test_template_service.py -v

# Compliance tests
python -m pytest tests/test_compliance_service.py -v

# Integration tests
python -m pytest tests/test_integration_generation.py -v

# All generation-related tests
python -m pytest tests/test_template_service.py tests/test_compliance_service.py tests/test_template_api.py tests/test_integration_generation.py -v
```

#### Run with coverage

```bash
# Install coverage tool if not already installed
pip install pytest-cov

# Run tests with coverage report
python -m pytest --cov=app --cov-report=term-missing --cov-report=html

# View HTML coverage report
# Open htmlcov/index.html in your browser
```

#### Test Statistics

- **Total Tests**: 47
- **Pass Rate**: 100%
- **Test Coverage**: Comprehensive coverage of all major features

---

## 🐳 Docker Quick Start

### Build and run services

```bash
docker compose up --build -d
```

### Check health

```bash
curl http://localhost:8000/health
# Expected: {"status":"ok", ...}
```

### View logs

```bash
# Follow logs
docker compose logs -f app

# View recent logs
docker compose logs --tail=100 app
```

### Stop and clean up

```bash
# Stop services
docker compose down

# Stop and remove volumes
docker compose down -v
```

---

## 🧪 Quick Testing Examples

### Example 1: Create and Test a Template

```bash
# 1. Create a template
curl -X POST "http://localhost:8000/templates" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test Notice",
    "template_type": "3day_notice",
    "category": "collections",
    "state": "CA",
    "content": "<h1>Notice to {{ tenant_name }}</h1><p>Amount due: {{ amount_due|currency }}</p>",
    "variables": {
      "tenant_name": {"type": "string", "required": true},
      "amount_due": {"type": "number", "required": true}
    }
  }'

# 2. Test render the template (replace TEMPLATE_ID with the ID from step 1)
curl -X POST "http://localhost:8000/templates/TEMPLATE_ID/test-render" \
  -H "Content-Type: application/json" \
  -d '{
    "tenant_name": "John Doe",
    "amount_due": 1500.00
  }'
```

### Example 2: Generate a Document

```bash
# Generate a document from template
curl -X POST "http://localhost:8000/documents/generate" \
  -H "Content-Type: application/json" \
  -d '{
    "template_id": "TEMPLATE_ID",
    "data": {
      "tenant_name": "Jane Smith",
      "amount_due": 2500.00,
      "property_address": "123 Main St"
    },
    "output_format": "html"
  }'

# Download the generated document (replace DOCUMENT_ID)
curl "http://localhost:8000/documents/DOCUMENT_ID/download" -o document.html
```

### Example 3: Check State Compliance

```bash
# Get compliance requirements for California
curl "http://localhost:8000/compliance/states/CA"

# Validate compliance for a document
curl "http://localhost:8000/compliance/validate?state=CA&document_type=3day_notice&notice_period_days=3"
```

### Example 4: Run Full Integration Test

```bash
# Run the complete integration test suite
python -m pytest tests/test_integration_generation.py::TestFullGenerationWorkflow::test_template_to_pdf_workflow -v -s
```

---

## 📋 API Endpoints

### Document Processing Endpoints

- `POST /documents/upload` - Upload a document for processing
- `GET /documents/{document_id}` - Get document metadata and status
- `GET /documents/{document_id}/text` - Extract text (plain, JSON, or Markdown)
- `POST /documents/{document_id}/parse` - Parse document (invoice, receipt, contract)

### Template Management Endpoints

- `POST /templates` - Create a new template
- `GET /templates` - List templates (with filters)
- `GET /templates/{id}` - Get template details
- `PATCH /templates/{id}` - Update template (creates new version)
- `POST /templates/{id}/test-render` - Test template rendering

### Document Generation Endpoints

- `POST /documents/generate` - Generate document from template
- `GET /documents/{id}/metadata` - Get generated document metadata
- `GET /documents/{id}/download` - Download generated document
- `POST /documents/{id}/regenerate` - Regenerate with new data

### E-Signature Endpoints

- `POST /documents/{id}/send-for-signature` - Send document for signature
- `GET /documents/{id}/signature-status` - Check signature status
- `POST /webhooks/pdffiller` - PDFfiller webhook handler

### Compliance Endpoints

- `GET /compliance/states` - List all state requirements
- `GET /compliance/states/{state}` - Get specific state requirements
- `POST /compliance/validate` - Validate document compliance
- `GET /compliance/template/{id}/validate` - Validate template compliance
- `GET /compliance/template/recommend` - Get recommended template

### Utility Endpoints

- `GET /health` - Health check endpoint

### Supported File Types and Limits

- **Types**: PDF, PNG, JPG, DOCX
- **Max file size**: 10 MB (oversized uploads return HTTP 400)

---

## 🔄 Workflows

### Document Processing Workflow

```bash
# 1) Upload a document
curl -s -X POST "http://localhost:8000/documents/upload" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@/path/to/file.pdf" | tee upload.json

# 2) Extract document ID
DOC_ID=$(python - <<'PY'
import sys, json
print(json.load(open('upload.json'))['document_id'])
PY
)

# 3) Poll status until completed/failed
while true; do
  BODY=$(curl -s "http://localhost:8000/documents/$DOC_ID")
  echo "$BODY" | grep -q '"status":"completed"' && break
  echo "$BODY" | grep -q '"status":"failed"' && break
  sleep 0.5
done

# 4) Get extracted text (as JSON)
curl -s "http://localhost:8000/documents/$DOC_ID/text?format=json"

# 5) Parse into structured fields (example: invoice)
curl -s -X POST "http://localhost:8000/documents/$DOC_ID/parse?parser_type=invoice"
```

### Document Generation Workflow

```bash
# 1) Create a template
TEMPLATE_RESPONSE=$(curl -s -X POST "http://localhost:8000/templates" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "3-Day Notice CA",
    "template_type": "3day_notice",
    "category": "collections",
    "state": "CA",
    "content": "<h1>3-Day Notice</h1><p>Dear {{ tenant_name }},</p><p>Amount due: {{ amount_due|currency }}</p>",
    "variables": {
      "tenant_name": {"type": "string", "required": true},
      "amount_due": {"type": "number", "required": true}
    }
  }')

# 2) Extract template ID
TEMPLATE_ID=$(echo $TEMPLATE_RESPONSE | python -c "import sys, json; print(json.load(sys.stdin)['id'])")

# 3) Generate document from template
DOC_RESPONSE=$(curl -s -X POST "http://localhost:8000/documents/generate" \
  -H "Content-Type: application/json" \
  -d "{
    \"template_id\": \"$TEMPLATE_ID\",
    \"data\": {
      \"tenant_name\": \"John Doe\",
      \"amount_due\": 1500.00
    },
    \"output_format\": \"html\"
  }")

# 4) Extract document ID
DOC_ID=$(echo $DOC_RESPONSE | python -c "import sys, json; print(json.load(sys.stdin)['document_id'])")

# 5) Download the generated document
curl "http://localhost:8000/documents/$DOC_ID/download" -o generated_notice.html

# 6) Send for signature (optional)
curl -s -X POST "http://localhost:8000/documents/$DOC_ID/send-for-signature" \
  -H "Content-Type: application/json" \
  -d '{
    "recipients": [
      {"email": "tenant@example.com", "name": "John Doe", "role": "signer"}
    ]
  }'
```

---

Sample OCR demo (using bundled test image)

- Prerequisite: API is running locally (uvicorn) or via Docker (docker compose up -d)
- Demo file: tests/sample_files/hello.png

```bash
# From the document-processor directory
# 1) Upload the sample image
curl -s -S -o upload_hello.json -w 'HTTP:%{http_code}\n' \
  -F 'file=@tests/sample_files/hello.png;type=image/png' \
  http://localhost:8000/documents/upload && \
  echo 'BODY:' && sed -n '1p' upload_hello.json

# 2) Extract the document_id
DOC_ID=$(python - <<'PY'
import json; print(json.load(open('upload_hello.json'))['document_id'])
PY
)

# 3) Poll until processing completes
for i in 1 2 3 4 5 6 7 8 9 10; do
  BODY=$(curl -s "http://localhost:8000/documents/$DOC_ID")
  echo poll:$i $BODY
  echo "$BODY" | grep -q '"status":"completed"' && break
  echo "$BODY" | grep -q '"status":"failed"' && break
  sleep 0.7
done

# 4) Get extracted text
curl -s "http://localhost:8000/documents/$DOC_ID/text?format=plain" | head -c 200; echo
```

## ⚙️ Configuration

### Environment Variables

- `DATABASE_PATH`: SQLite DB path (default: `app/app.db` inside container; `./app.db` locally)
- `APP_ENV`: `dev` | `prod` (controls error detail level)
- `SUPABASE_URL`: Supabase URL (optional, uses SQLite if not set)
- `SUPABASE_KEY`: Supabase API key (optional)
- `R2_ACCOUNT_ID`: Cloudflare R2 account ID (optional, uses local storage if not set)
- `R2_ACCESS_KEY_ID`: R2 access key (optional)
- `R2_SECRET_ACCESS_KEY`: R2 secret key (optional)
- `R2_BUCKET_NAME`: R2 bucket name (optional)
- `PDFFILLER_API_KEY`: PDFfiller API key (optional, uses mock if not set)
- `OPENAI_API_KEY`: OpenAI API key (optional, uses rule-based classification if not set)

### Rate Limiting

- **Default**: 10 requests/min per client (defined in `app/main.py`)
- **Configurable**: Modify `rl.max` in `app/main.py`

### Cache Settings

- **Text cache TTL**: 3600 seconds (see `app/api/routes.py`)

---

## 🏗️ Architecture Overview

### Core Components

- **FastAPI Application**: Main web framework with automatic OpenAPI documentation
- **API Routers**: Modular route organization (`app/api/`)
  - Template routes (`template_routes.py`)
  - Generation routes (`generation_routes.py`)
  - Signature routes (`signature_routes.py`)
  - Compliance routes (`compliance_routes.py`)
  - Integration routes (`integration_routes.py`)

### Services Layer

- **Template Service**: Jinja2 rendering with custom filters
- **Generation Service**: Document generation and PDF conversion
- **Storage Service**: Local/cloud storage abstraction
- **Signature Service**: E-signature workflow management
- **Classification Service**: AI-powered document classification
- **Compliance Service**: State-specific compliance validation
- **OCR Service**: Tesseract integration with circuit breaker
- **Parser Service**: Rule-based document parsing
- **Queue Service**: Background processing with retries

### Data Layer

- **SQLite Database**: Primary data store with WAL mode
- **Repositories**: Database access abstraction
  - `TemplateRepository`
  - `GeneratedDocumentRepository`
  - Document processing repositories

### Key Features

- **Health Checks**: Deep dependency probes
- **Rate Limiting**: Token bucket algorithm
- **Error Handling**: Comprehensive exception handling
- **Logging**: Structured logging throughout
- **Testing**: 47 tests with 100% pass rate

---

## 🧪 Testing & Coverage

### Test Statistics

- **Total Tests**: 47
- **Pass Rate**: 100%
- **Coverage**: Comprehensive coverage of all major features
- **Minimum Coverage**: ≥70% enforced via `pytest.ini`

### Running Tests

```bash
# Run all tests
python -m pytest -v

# Run with coverage
python -m pytest --cov=app --cov-report=term-missing --cov-report=html

# Run specific test suites
python -m pytest tests/test_template_service.py -v
python -m pytest tests/test_compliance_service.py -v
python -m pytest tests/test_integration_generation.py -v
```

### Test Suites

- **Template Service Tests** (`test_template_service.py`): 16 tests
- **Compliance Service Tests** (`test_compliance_service.py`): 13 tests
- **Template API Tests** (`test_template_api.py`): 11 tests
- **Integration Tests** (`test_integration_generation.py`): 7 tests

---

## 🔧 Troubleshooting

### Common Issues

#### 429 Too Many Requests

**Problem**: You hit the per-client rate limit (10/min).
**Solution**: Wait ~60 seconds and retry, or increase the rate limit in `app/main.py`.

#### 409 Conflict on Parse

**Problem**: Parsing requires the document to be processed first.
**Solution**: Poll `GET /documents/{id}` until status is `"completed"`.

#### OCR Errors Locally

**Problem**: Tesseract is not installed on your system.
**Solution**:

- Use Docker (includes tesseract-ocr)
- Install Tesseract:
  - **Windows**: Download from [GitHub](https://github.com/UB-Mannheim/tesseract/wiki)
  - **Mac**: `brew install tesseract`
  - **Linux**: `sudo apt-get install tesseract-ocr`

#### PDF Generation Fails on Windows

**Problem**: WeasyPrint requires system libraries not available on Windows.
**Solution**:

- Use Docker for full PDF support
- Use `"output_format": "html"` instead of `"pdf"`
- Install GTK+ libraries (advanced)

#### Docker Health Issues

**Problem**: Container is unhealthy or not starting.
**Solution**:

```bash
# Check container status
docker compose ps

# View logs
docker compose logs -f app

# Restart services
docker compose restart

# Rebuild from scratch
docker compose down -v
docker compose up --build
```

#### Database Locked Errors

**Problem**: SQLite database is locked.
**Solution**:

- Ensure only one instance is running
- Check for zombie processes
- Delete `app.db-wal` and `app.db-shm` files if safe

---

## 📝 Notes & Limitations

### Current Limitations

- **PyPDF2 Deprecation**: Migration to `pypdf` is planned for a future iteration
- **In-Memory Queue**: Suitable for single-instance use; for multi-instance scaling, switch to Redis-backed queue
- **Mock Services**: Current implementation uses mock services for:
  - Supabase (uses SQLite)
  - Cloudflare R2/S3 (uses local file storage)
  - PDFfiller (uses in-memory mock)
  - OpenAI (uses rule-based classification)

### Production Deployment

For production deployment, replace mock services with real implementations:

1. **Database**: Configure Supabase connection
2. **Storage**: Set up Cloudflare R2 or AWS S3
3. **E-Signature**: Configure PDFfiller API credentials
4. **AI Classification**: Set up OpenAI API key
5. **Security**: Add authentication (API keys, JWT)
6. **Monitoring**: Set up logging and monitoring
7. **HTTPS**: Enable SSL/TLS

See [Implementation Summary](docs/IMPLEMENTATION_SUMMARY.md) for detailed deployment instructions.

---

## 📄 License

This project is part of a property management document processing system.

## 🤝 Contributing

For questions or contributions, please refer to the project documentation in the `docs/` folder.
