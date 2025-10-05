# Document Processing & Generation API Documentation

## Overview

This service provides comprehensive document processing and generation capabilities for property management:

- **Document Processing**: Upload, OCR, and classify documents
- **Template Management**: Create and manage document templates
- **Document Generation**: Generate PDFs from templates
- **E-Signature**: Send documents for electronic signature
- **Compliance**: State-specific compliance validation

## Base URL

```
http://localhost:8000
```

## API Endpoints

### Health Check

#### GET /health

Check service health and dependencies.

**Response:**
```json
{
  "status": "ok",
  "dependencies": {
    "db": "ok",
    "pdfplumber": "ok",
    "pypdf": "ok",
    "pytesseract": "ok",
    "tesseract_binary": "ok"
  }
}
```

---

## Template Management

### POST /templates

Create a new document template.

**Request Body:**
```json
{
  "template_type": "payment_notice",
  "name": "3-Day Notice - California",
  "category": "collections",
  "state": "CA",
  "template_content": "<html>...</html>",
  "variables": [
    {
      "name": "tenant_name",
      "type": "string",
      "required": true,
      "description": "Tenant's full name"
    },
    {
      "name": "amount_owed",
      "type": "currency",
      "required": true
    }
  ],
  "requires_signature": true,
  "legal_compliance_notes": "California Civil Code Section 1161"
}
```

**Response:**
```json
{
  "id": "uuid",
  "template_type": "payment_notice",
  "version": 1,
  "status": "active",
  "created_at": "2025-10-03T10:00:00Z"
}
```

### GET /templates

List all templates with optional filters.

**Query Parameters:**
- `category` (optional): Filter by category (collections, maintenance, leasing)
- `state` (optional): Filter by state code
- `template_type` (optional): Filter by template type
- `active_only` (optional): Only return active templates (default: true)

**Example:**
```bash
curl "http://localhost:8000/templates?category=collections&state=CA"
```

### GET /templates/{template_id}

Get a specific template by ID.

**Response:**
```json
{
  "id": "uuid",
  "template_type": "payment_notice",
  "name": "3-Day Notice - California",
  "category": "collections",
  "state": "CA",
  "version": 1,
  "template_content": "<html>...</html>",
  "variables": [...],
  "requires_signature": true,
  "status": "active",
  "created_at": "2025-10-03T10:00:00Z"
}
```

### PATCH /templates/{template_id}

Update a template (creates new version).

**Request Body:**
```json
{
  "name": "Updated Template Name",
  "status": "deprecated"
}
```

### POST /templates/{template_id}/test-render

Test render a template with sample data.

**Request Body:**
```json
{
  "data": {
    "tenant_name": "John Smith",
    "amount_owed": "1500.00",
    "property_address": "123 Main St",
    "current_date": "2025-10-03"
  }
}
```

**Response:**
```json
{
  "template_id": "uuid",
  "rendered_html": "<html>...</html>",
  "validation_errors": [],
  "success": true
}
```

---

## Document Generation

### POST /documents/generate

Generate a document from a template.

**Request Body:**
```json
{
  "template_id": "uuid",
  "data": {
    "tenant_name": "John Smith",
    "unit_name": "101",
    "property_name": "Sunset Apartments",
    "property_address": "123 Main St, Los Angeles, CA 90001",
    "amount_owed": "1500.00",
    "tenant_portion": "500.00",
    "delinquent_from": "2025-09-01",
    "payment_deadline": "2025-10-06",
    "manager_name": "Jane Manager",
    "manager_phone": "555-123-4567"
  },
  "output_format": "pdf",
  "metadata": {
    "tenant_id": 12345,
    "property_id": 67890,
    "created_by": "collections_workflow"
  },
  "requires_signature": true,
  "signature_recipients": [
    {
      "email": "tenant@example.com",
      "name": "John Smith",
      "role": "tenant"
    }
  ]
}
```

**Response:**
```json
{
  "document_id": "uuid",
  "status": "generated",
  "document_url": "http://localhost:8000/storage/documents/collections/uuid/file.pdf",
  "signature_status": "pending",
  "signature_envelope_id": null,
  "created_at": "2025-10-03T10:00:00Z"
}
```

### GET /documents/{document_id}/metadata

Get document metadata.

**Response:**
```json
{
  "document_id": "uuid",
  "filename": "payment_notice_20251003_100000.pdf",
  "template_id": "uuid",
  "template_type": "payment_notice",
  "category": "collections",
  "tenant_id": 12345,
  "property_id": 67890,
  "created_by": "system",
  "requires_signature": true,
  "signature_status": "pending",
  "file_size": 45678,
  "created_at": "2025-10-03T10:00:00Z"
}
```

### GET /documents/{document_id}/download

Download a generated document.

**Response:** Binary PDF file

**Example:**
```bash
curl -O "http://localhost:8000/documents/{document_id}/download"
```

### POST /documents/{document_id}/regenerate

Regenerate a document with new data.

**Request Body:**
```json
{
  "tenant_name": "John Smith",
  "amount_owed": "1200.00"
}
```

---

## E-Signature

### POST /documents/{document_id}/send-for-signature

Send a document for e-signature.

**Request Body:**
```json
{
  "signature_recipients": [
    {
      "email": "tenant@example.com",
      "name": "John Smith",
      "role": "tenant"
    },
    {
      "email": "manager@example.com",
      "name": "Property Manager",
      "role": "manager"
    }
  ]
}
```

**Response:**
```json
{
  "document_id": "uuid",
  "signature_request_id": "mock_sig_abc123",
  "status": "pending",
  "envelope_url": "https://mock.pdffiller.com/sign/abc123",
  "recipients": [
    {
      "email": "tenant@example.com",
      "name": "John Smith",
      "role": "tenant",
      "status": "pending"
    }
  ]
}
```

### GET /documents/{document_id}/signature-status

Get signature status for a document.

**Response:**
```json
{
  "document_id": "uuid",
  "signature_status": "pending",
  "signature_request_id": "mock_sig_abc123",
  "signed_at": null,
  "recipients_status": [
    {
      "email": "tenant@example.com",
      "name": "John Smith",
      "status": "pending",
      "signed_at": null
    }
  ]
}
```

### POST /webhooks/pdffiller

Webhook handler for PDFfiller signature events (for production use).

---

## Document Processing & Classification

### POST /documents/upload

Upload a document for OCR processing (existing functionality).

**Request:** Multipart form data with file

**Response:**
```json
{
  "document_id": "uuid",
  "status": "pending"
}
```

### POST /documents/process-and-classify

Upload and classify a document in one step.

**Request:** Multipart form data with file

**Response:**
```json
{
  "document_id": "uuid",
  "type": "lease_agreement",
  "confidence": 0.85,
  "extracted_fields": {
    "tenant_name": "John Smith",
    "monthly_rent": "1500",
    "lease_term": "12 months"
  }
}
```

---

## Compliance

### GET /compliance/states

Get state-specific compliance requirements.

**Query Parameters:**
- `state` (optional): Filter by specific state code

**Response:**
```json
[
  {
    "state": "CA",
    "notice_days": 3,
    "legal_reference": "California Civil Code Section 1161",
    "required_fields": ["amount_owed", "payment_deadline", "property_address", "tenant_name"],
    "special_requirements": [
      "Must include CCP reference",
      "Must be served in person or by certified mail"
    ]
  }
]
```

### POST /compliance/validate

Validate document data against state requirements.

**Request Body:**
```json
{
  "template_type": "payment_notice",
  "state": "CA",
  "data": {
    "amount_owed": "1500.00",
    "payment_deadline": "2025-10-06",
    "property_address": "123 Main St",
    "tenant_name": "John Smith"
  }
}
```

**Response:**
```json
{
  "compliant": true,
  "issues": [],
  "legal_reference": "California Civil Code Section 1161",
  "special_requirements": [...]
}
```

---

## Error Responses

All endpoints return standard HTTP status codes:

- `200 OK`: Success
- `400 Bad Request`: Invalid input
- `404 Not Found`: Resource not found
- `409 Conflict`: Resource state conflict
- `429 Too Many Requests`: Rate limit exceeded
- `500 Internal Server Error`: Server error

**Error Response Format:**
```json
{
  "detail": "Error message description"
}
```

---

## Rate Limiting

- **Limit:** 10 requests per minute per client IP
- **Response:** HTTP 429 when exceeded
- **Reset:** 60 seconds

---

## Authentication

Currently, the service does not require authentication. In production, implement:
- API key authentication
- JWT tokens
- OAuth 2.0

---

## Examples

### Complete Workflow: Generate and Send for Signature

```bash
# 1. Create a template (or use existing)
TEMPLATE_ID="existing-template-uuid"

# 2. Generate document
curl -X POST "http://localhost:8000/documents/generate" \
  -H "Content-Type: application/json" \
  -d '{
    "template_id": "'$TEMPLATE_ID'",
    "data": {
      "tenant_name": "John Smith",
      "amount_owed": "1500.00",
      "property_address": "123 Main St"
    },
    "requires_signature": true
  }' | jq -r '.document_id' > doc_id.txt

DOC_ID=$(cat doc_id.txt)

# 3. Send for signature
curl -X POST "http://localhost:8000/documents/$DOC_ID/send-for-signature" \
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

# 4. Check signature status
curl "http://localhost:8000/documents/$DOC_ID/signature-status"
```

---

## Interactive API Documentation

Visit `http://localhost:8000/docs` for interactive Swagger UI documentation.

