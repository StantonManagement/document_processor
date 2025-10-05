# Quick Start Guide - Document Generation Agent

## Prerequisites

- Python 3.10+ (or Docker)
- Git Bash (Windows) or Terminal (Mac/Linux)

## Option 1: Local Development (Recommended for Testing)

### 1. Setup Environment

```bash
cd document-processor

# Create virtual environment
python -m venv .venv

# Activate virtual environment
# Git Bash (Windows):
source .venv/Scripts/activate
# CMD (Windows):
.venv\Scripts\activate
# Mac/Linux:
source .venv/bin/activate

# Install dependencies using uv (faster) or pip
uv pip install -r requirements.txt
# OR
pip install -r requirements.txt
```

### 2. Run Tests

```bash
# Run all tests
python -m pytest

# Run specific test file
python -m pytest tests/test_template_service.py -v

# Run with coverage (if pytest-cov installed)
python -m pytest --cov=app
```

### 3. Start the Server

```bash
uvicorn app.main:app --reload
```

The API will be available at `http://localhost:8000`

### 4. Access Interactive Documentation

Open your browser and visit:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Option 2: Docker (Recommended for Production)

### 1. Build Docker Image

```bash
cd document-processor
docker build -t document-processor .
```

### 2. Run Container

```bash
docker run -p 8000:8000 document-processor
```

### 3. Access the API

Visit `http://localhost:8000/docs`

## Quick API Examples

### Example 1: Create a Template

```bash
curl -X POST "http://localhost:8000/templates" \
  -H "Content-Type: application/json" \
  -d '{
    "template_type": "payment_notice",
    "name": "3-Day Notice - California",
    "category": "collections",
    "state": "CA",
    "template_content": "<html><body><h1>Payment Notice</h1><p>Dear {{ tenant_name }},</p><p>You owe {{ amount_owed|currency }}</p></body></html>",
    "variables": [
      {
        "name": "tenant_name",
        "type": "string",
        "required": true,
        "description": "Tenant full name"
      },
      {
        "name": "amount_owed",
        "type": "currency",
        "required": true,
        "description": "Amount owed"
      }
    ],
    "requires_signature": false
  }'
```

### Example 2: List Templates

```bash
curl "http://localhost:8000/templates"
```

### Example 3: Generate a Document

```bash
# First, get a template ID from the list above, then:
curl -X POST "http://localhost:8000/documents/generate" \
  -H "Content-Type: application/json" \
  -d '{
    "template_id": "YOUR_TEMPLATE_ID_HERE",
    "data": {
      "tenant_name": "John Smith",
      "amount_owed": "1500.00",
      "property_address": "123 Main St, Los Angeles, CA 90001",
      "unit_name": "101",
      "current_date": "2025-10-03"
    },
    "output_format": "html",
    "metadata": {
      "tenant_id": 12345,
      "property_id": 67890
    }
  }'
```

### Example 4: Download Generated Document

```bash
# Use the document_id from the generate response
curl -O "http://localhost:8000/documents/{document_id}/download"
```

### Example 5: Check State Compliance Requirements

```bash
curl "http://localhost:8000/compliance/states?state=CA"
```

### Example 6: Validate Document Compliance

```bash
curl -X POST "http://localhost:8000/compliance/validate" \
  -H "Content-Type: application/json" \
  -d '{
    "template_type": "payment_notice",
    "state": "CA",
    "data": {
      "amount_owed": "1500.00",
      "payment_deadline": "2025-10-06",
      "property_address": "123 Main St",
      "tenant_name": "John Smith"
    }
  }'
```

## Using the Sample Templates

The service includes pre-built templates in `app/templates/`:

1. **3-Day Notice (CA)** - California payment notice
2. **14-Day Notice (NY)** - New York payment notice
3. **3-Day Notice (TX)** - Texas payment notice
4. **Work Order** - Maintenance work order
5. **Payment Plan Agreement** - Payment plan contract

To use these templates, you need to load them into the database first. You can do this by creating templates via the API using the HTML content from these files.

## Common Tasks

### Health Check

```bash
curl "http://localhost:8000/health"
```

### Test Template Rendering

```bash
curl -X POST "http://localhost:8000/templates/{template_id}/test-render" \
  -H "Content-Type: application/json" \
  -d '{
    "data": {
      "tenant_name": "Test User",
      "amount_owed": "1000.00"
    }
  }'
```

### Send Document for Signature (Mock)

```bash
curl -X POST "http://localhost:8000/documents/{document_id}/send-for-signature" \
  -H "Content-Type: application/json" \
  -d '{
    "signature_recipients": [
      {
        "email": "tenant@example.com",
        "name": "John Smith",
        "role": "tenant"
      }
    ]
  }'
```

### Check Signature Status

```bash
curl "http://localhost:8000/documents/{document_id}/signature-status"
```

## Troubleshooting

### Issue: "ModuleNotFoundError: No module named 'jinja2'"

**Solution:** Install dependencies
```bash
pip install -r requirements.txt
```

### Issue: "WeasyPrint cannot load library" (Windows)

**Solution:** Use Docker or HTML output format instead of PDF
```json
{
  "output_format": "html"
}
```

### Issue: "Database is locked"

**Solution:** Only one process can write to SQLite at a time. Stop other instances or use a different database path.

### Issue: Rate limit exceeded

**Solution:** Wait 60 seconds or adjust `RATE_LIMIT_PER_MINUTE` in environment variables.

## Environment Variables

Create a `.env` file in the `document-processor` directory:

```env
DATABASE_PATH=./app/app.db
APP_ENV=dev
STORAGE_PATH=./app/storage
RATE_LIMIT_PER_MINUTE=10
```

## Next Steps

1. **Explore the API**: Visit `http://localhost:8000/docs` for interactive documentation
2. **Read the Full API Docs**: See `API_DOCUMENTATION.md`
3. **Review Sample Templates**: Check `app/templates/` directory
4. **Run Tests**: Execute `python -m pytest` to see all tests pass
5. **Customize Templates**: Create your own templates using Jinja2 syntax

## Support

For detailed information, see:
- `API_DOCUMENTATION.md` - Complete API reference
- `IMPLEMENTATION_SUMMARY.md` - Implementation details
- `README.md` - Original project documentation

## Production Deployment

Before deploying to production:

1. Replace mock services with real implementations
2. Add authentication (API keys, JWT)
3. Configure real database (PostgreSQL recommended)
4. Set up cloud storage (S3, R2)
5. Configure monitoring and logging
6. Enable HTTPS
7. Set up CI/CD pipeline

See `IMPLEMENTATION_SUMMARY.md` for more details on production readiness.

