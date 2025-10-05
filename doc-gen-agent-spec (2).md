```

### 5. Document Storage & Retrieval

**Storage Strategy:**
```python
from supabase import create_client
import boto3  # or use Cloudflare R2

class DocumentStorage:
    def __init__(self):
        self.supabase = create_client(
            os.getenv("SUPABASE_URL"),
            os.getenv("SUPABASE_KEY")
        )
        # Use Cloudflare R2 (S3-compatible) for file storage
        self.s3_client = boto3.client(
            's3',
            endpoint_url=os.getenv("R2_ENDPOINT"),
            aws_access_key_id=os.getenv("R2_ACCESS_KEY"),
            aws_secret_access_key=os.getenv("R2_SECRET_KEY")
        )
        self.bucket_name = os.getenv("R2_BUCKET_NAME")
    
    async def store_document(
        self,
        document_id: str,
        document_bytes: bytes,
        filename: str,
        metadata: dict
    ) -> str:
        # Store file in R2
        s3_key = f"documents/{metadata['category']}/{document_id}/{filename}"
        self.s3_client.put_object(
            Bucket=self.bucket_name,
            Key=s3_key,
            Body=document_bytes,
            ContentType='application/pdf'
        )
        
        # Store metadata in Supabase
        result = self.supabase.table('generated_documents').insert({
            'id': document_id,
            'filename': filename,
            'storage_key': s3_key,
            'template_id': metadata.get('template_id'),
            'template_type': metadata.get('template_type'),
            'category': metadata.get('category'),
            'tenant_id': metadata.get('tenant_id'),
            'property_id': metadata.get('property_id'),
            'created_by': metadata.get('created_by'),
            'workflow_id': metadata.get('workflow_id'),
            'requires_signature': metadata.get('requires_signature', False),
            'signature_status': 'not_required' if not metadata.get('requires_signature') else 'pending',
            'file_size': len(document_bytes),
            'metadata': metadata
        }).execute()
        
        # Generate presigned URL for download
        url = self.s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': self.bucket_name, 'Key': s3_key},
            ExpiresIn=3600  # 1 hour
        )
        
        return url
    
    async def get_document_url(self, document_id: str, expires_in: int = 3600) -> str:
        # Get storage key from Supabase
        result = self.supabase.table('generated_documents')\
            .select('storage_key')\
            .eq('id', document_id)\
            .execute()
        
        if not result.data:
            raise HTTPException(status_code=404, detail="Document not found")
        
        storage_key = result.data[0]['storage_key']
        
        # Generate presigned URL
        url = self.s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': self.bucket_name, 'Key': storage_key},
            ExpiresIn=expires_in
        )
        
        return url
```

### 6. Integration with Gabriel's Document Processing

**Combine Intake and Generation:**
```python
@router.post("/documents/process-and-classify")
async def process_uploaded_document(file: UploadFile):
    """
    Use Gabriel's OCR service to process uploaded documents,
    then classify and store them
    """
    # Call Gabriel's document processing service
    async with httpx.AsyncClient() as client:
        files = {"file": (file.filename, await file.read(), file.content_type)}
        response = await client.post(
            f"{os.getenv('DOC_PROCESSING_URL')}/documents/upload",
            files=files
        )
        
        if response.status_code != 200:
            raise HTTPException(status_code=500, detail="Document processing failed")
        
        processing_result = response.json()
    
    # Wait for processing to complete
    document_id = processing_result["document_id"]
    extracted_text = await wait_for_extraction(document_id)
    
    # Classify document type using AI
    classification = await classify_document(extracted_text)
    
    # Store with proper categorization
    await store_processed_document(
        document_id=document_id,
        filename=file.filename,
        document_type=classification["type"],
        extracted_data=classification["extracted_fields"],
        confidence=classification["confidence"]
    )
    
    return {
        "document_id": document_id,
        "type": classification["type"],
        "confidence": classification["confidence"],
        "extracted_fields": classification["extracted_fields"]
    }

async def classify_document(text: str) -> dict:
    """Use OpenAI to classify document type and extract key fields"""
    client = openai.AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    
    completion = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": """Classify this property management document and extract key fields.
                
                Document types:
                - lease_agreement
                - work_order
                - payment_receipt
                - maintenance_report
                - court_notice
                - tenant_application
                
                Return JSON with: type, confidence (0-1), extracted_fields (relevant data)"""
            },
            {
                "role": "user",
                "content": f"Document text:\n\n{text[:2000]}"  # Limit tokens
            }
        ],
        response_format={"type": "json_object"}
    )
    
    return json.loads(completion.choices[0].message.content)
```

### 7. State-Specific Compliance

**Template Variants by State:**
```python
class ComplianceManager:
    # State-specific requirements for eviction notices
    STATE_RULES = {
        "CA": {
            "notice_days": 3,
            "legal_reference": "California Civil Code Section 1161",
            "required_fields": ["amount_owed", "payment_deadline", "property_address"],
            "special_requirements": ["Must include CCP reference", "Must be served in person"]
        },
        "NY": {
            "notice_days": 14,
            "legal_reference": "NY Real Property Law § 711",
            "required_fields": ["amount_owed", "payment_deadline", "property_address", "court_info"],
            "special_requirements": ["Must include court information", "Must mention right to legal aid"]
        },
        "TX": {
            "notice_days": 3,
            "legal_reference": "Texas Property Code § 24.005",
            "required_fields": ["amount_owed", "payment_deadline", "property_address"],
            "special_requirements": ["Notice of right to cure", "Must be delivered by specific methods"]
        }
    }
    
    def get_template_for_state(self, template_type: str, state: str):
        """Get correct template variant based on state"""
        result = self.supabase.table('templates')\
            .select('*')\
            .eq('template_type', template_type)\
            .eq('state', state)\
            .eq('status', 'active')\
            .order('version', desc=True)\
            .limit(1)\
            .execute()
        
        if not result.data:
            # Fallback to generic template
            return self.get_generic_template(template_type)
        
        return result.data[0]
    
    def validate_compliance(self, template_type: str, state: str, data: dict) -> dict:
        """Validate that generated document meets state requirements"""
        rules = self.STATE_RULES.get(state, {})
        issues = []
        
        for required_field in rules.get("required_fields", []):
            if required_field not in data or not data[required_field]:
                issues.append(f"Missing required field: {required_field}")
        
        return {
            "compliant": len(issues) == 0,
            "issues": issues,
            "legal_reference": rules.get("legal_reference"),
            "special_requirements": rules.get("special_requirements", [])
        }
```

## Database Schema

```sql
-- Templates table
CREATE TABLE document_templates (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    template_type text NOT NULL,
    name text NOT NULL,
    category text NOT NULL,  -- collections, maintenance, leasing
    state text,  -- State-specific templates (NULL for generic)
    version integer DEFAULT 1,
    template_content text NOT NULL,  -- HTML/Jinja2 template
    variables jsonb NOT NULL,  -- Variable definitions
    requires_signature boolean DEFAULT false,
    legal_compliance_notes text,
    status text DEFAULT 'active',  -- active, deprecated, archived
    created_by text,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    
    UNIQUE(template_type, state, version)
);

-- Generated documents table
CREATE TABLE generated_documents (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    filename text NOT NULL,
    storage_key text NOT NULL,  -- S3/R2 key
    template_id uuid REFERENCES document_templates(id),
    template_type text,
    category text NOT NULL,
    
    -- Linking
    tenant_id bigint,
    property_id bigint,
    unit_id bigint,
    
    -- Workflow tracking
    created_by text NOT NULL,
    workflow_id uuid,
    
    -- Signature tracking
    requires_signature boolean DEFAULT false,
    signature_status text,  -- not_required, pending, signed, declined, expired
    signature_request_id text,  -- PDFfiller signature request ID
    signed_at timestamp with time zone,
    signed_document_key text,  -- S3 key for signed version
    
    -- Metadata
    file_size bigint,
    metadata jsonb,
    
    -- Timestamps
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    
    INDEX idx_tenant_id (tenant_id),
    INDEX idx_template_type (template_type),
    INDEX idx_signature_status (signature_status)
);

-- Document access log (audit trail)
CREATE TABLE document_access_log (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id uuid REFERENCES generated_documents(id),
    accessed_by text NOT NULL,
    access_type text NOT NULL,  -- view, download, generate, sign
    ip_address text,
    created_at timestamp with time zone DEFAULT now()
);
```

## API Endpoints Summary

```
Template Management:
POST   /templates                    - Create template
GET    /templates                    - List templates
GET    /templates/{id}               - Get template
PATCH  /templates/{id}               - Update template (creates new version)
POST   /templates/{id}/test-render   - Test rendering

Document Generation:
POST   /documents/generate           - Generate document from template
GET    /documents/{id}               - Get document metadata
GET    /documents/{id}/download      - Download document
POST   /documents/{id}/regenerate    - Regenerate with new data

Document Processing (integration with Gabriel's service):
POST   /documents/process-and-classify  - OCR + classification

E-Signature:
POST   /documents/{id}/send-for-signature  - Send via PDFfiller
GET    /documents/{id}/signature-status    - Check signature status
POST   /webhooks/pdffiller                 - PDFfiller webhook handler

Utility:
GET    /health                       - Health check
GET    /compliance/states            - List state-specific requirements
POST   /compliance/validate          - Validate document compliance
```

## Testing Requirements

### Unit Tests
- Template rendering with Jinja2
- PDF generation from HTML
- Variable substitution
- State-specific template selection
- Compliance validation

### Integration Tests
- Full generation workflow (template → data → PDF)
- PDFfiller API integration
- Storage and retrieval
- Integration with Gabriel's OCR service
- Webhook handling

### Test Templates
Include at least 3 production-ready templates:
1. 3-Day Payment Notice (CA, NY, TX variants)
2. Work Order (generic)
3. Payment Plan Agreement (generic)

## Performance Requirements
- Template rendering < 2 seconds
- PDF generation < 5 seconds
- Signature request creation < 3 seconds
- Support 50 concurrent generations
- Cache rendered templates for 1 hour

## Environment Variables

```env
# Supabase
SUPABASE_URL=https://[project].supabase.co
SUPABASE_KEY=[service-key]

# Storage (Cloudflare R2 or AWS S3)
R2_ENDPOINT=https://[account-id].r2.cloudflarestorage.com
R2_ACCESS_KEY=[access-key]
R2_SECRET_KEY=[secret-key]
R2_BUCKET_NAME=property-docs

# PDFfiller
PDFFILLER_CLIENT_ID=[client-id]
PDFFILLER_CLIENT_SECRET=[client-secret]

# OpenAI (for classification)
OPENAI_API_KEY=sk-...

# Gabriel's Document Processing Service
DOC_PROCESSING_URL=http://localhost:8005

# App
APP_URL=https://yourapp.com
```

## Success Criteria

- [ ] Template CRUD operations working
- [ ] Jinja2 rendering functional
- [ ] PDF generation from HTML templates
- [ ] PDFfiller integration complete
- [ ] Signature workflow end-to-end
- [ ] Document storage (R2/S3) working
- [ ] Integration with Gabriel's OCR service
- [ ] State-specific template variants
- [ ] Compliance validation
- [ ] 80% test coverage
- [ ] 3+ production-ready templates included
- [ ] Webhook handler functional
- [ ] Documentation complete

## Deliverables

1. **GitHub Repository** with:
   - Complete FastAPI application
   - Sample templates (HTML/Jinja2)
   - Requirements.txt
   - .env.example
   - README with setup instructions
   - Test suite with 80%+ coverage
   - Docker configuration

2. **Documentation**:
   - API documentation with curl examples
   - Template creation guide
   - Integration guide for other services
   - State compliance reference
   - PDFfiller setup instructions

3. **Sample Templates**:
   - 3-Day Notice (CA, NY, TX)
   - Work Order
   - Payment Plan Agreement

## Common Pitfalls to Avoid

- PDF generation can be memory-intensive - use streaming where possible
- PDFfiller API has rate limits - implement backoff
- Template variable types must match data types
- State compliance changes - version templates properly
- Signature webhooks may arrive multiple times - handle idempotently
- Presigned URLs expire - regenerate as needed
- Don't store PDFs in database - use object storage

## Questions to Consider

- Should we support DOCX output in addition to PDF?
- Do we need template preview functionality?
- Should signatures be required in sequence or parallel?
- How long should we keep generated documents?
- Do we need template approval workflow?
- Should we support merge fields for bulk generation?

## Starting Instructions

Reply with "Starting Document Generation Agent - 72 hour timer begins" to start.

Gabriel - you're extending your existing work. Focus on the generation side since you already have intake covered. The PDFfiller integration is the new challenge here.# Document Generation Agent - Project Specification

## Project Overview
Build a FastAPI service that generates property management documents from templates and structured data. This extends Gabriel's document processing work by adding template-based generation, e-signature routing, and document storage management.

## Payment & Timeline
- **Payment**: $125 flat fee
- **Timeline**: 72 hours from start confirmation
- **Quality Bonus**: Additional $25 for e-signature integration working + 80%+ test coverage
- **Total Potential**: $150

## Business Context
Property management requires generating dozens of document types:
- **Collections**: Payment notices, demand letters, settlement agreements, court filings
- **Maintenance**: Work orders, completion reports, vendor contracts
- **Leasing**: Lease agreements, addendums, move-in/move-out forms, applications

This agent provides:
1. Template management and rendering
2. PDF generation from data + templates
3. Document storage and retrieval
4. E-signature workflow integration
5. State-specific compliance templates

## Relationship to Gabriel's Work

**You're extending Gabriel's document processing service:**
- His OCR/extraction → Your document intake branch
- His parsing logic → Your document classification
- His storage patterns → Your document management
- Add new: Template rendering, PDF generation, e-signatures

**Architecture:**
```
Document Generation Agent
├── Intake Branch (uses Gabriel's OCR service)
├── Generate Branch (NEW - template + data → PDF)
├── Store Branch (extends Gabriel's storage)
└── Sign Branch (NEW - e-signature routing)
```

## Core Requirements

### 1. Template Management

**POST /templates**
```json
{
  "template_type": "payment_notice",
  "name": "3-Day Notice - Standard",
  "category": "collections",
  "state": "CA",
  "template_content": "base64_encoded_html_or_docx",
  "variables": [
    {
      "name": "tenant_name",
      "type": "string",
      "required": true
    },
    {
      "name": "amount_owed",
      "type": "currency",
      "required": true
    },
    {
      "name": "due_date",
      "type": "date",
      "required": true
    }
  ],
  "requires_signature": true,
  "legal_compliance_notes": "California CCP Section 1161"
}

Response:
{
  "id": "uuid",
  "template_type": "payment_notice",
  "version": 1,
  "status": "active",
  "created_at": "2025-09-30T10:00:00Z"
}
```

**GET /templates**
Query parameters:
- `category`: collections, maintenance, leasing
- `state`: Filter by state-specific templates
- `template_type`: Specific document type
- `active_only`: Boolean

**GET /templates/{id}**
Get template with full metadata

**PATCH /templates/{id}**
Update template (creates new version)

**POST /templates/{id}/test-render**
Test template rendering with sample data

### 2. Document Generation

**POST /documents/generate**
```json
{
  "template_id": "uuid",
  "data": {
    "tenant_name": "John Smith",
    "unit_name": "101",
    "property_name": "Sunset Apartments",
    "amount_owed": "1500.00",
    "tenant_portion": "500.00",
    "due_date": "2025-10-05",
    "payment_plan": {
      "weekly_amount": "200.00",
      "number_of_weeks": 8,
      "start_date": "2025-10-10"
    }
  },
  "output_format": "pdf",
  "metadata": {
    "tenant_id": 12345,
    "property_id": 67890,
    "created_by": "collections_workflow",
    "workflow_id": "uuid"
  },
  "requires_signature": true,
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

Response:
{
  "document_id": "uuid",
  "status": "generated",
  "document_url": "https://storage.../document.pdf",
  "signature_status": "pending",
  "signature_envelope_id": "docusign_envelope_id",
  "created_at": "2025-09-30T10:00:00Z"
}
```

**GET /documents/{document_id}**
Get document metadata and download URL

**GET /documents/{document_id}/download**
Stream document file

**POST /documents/{document_id}/regenerate**
Regenerate document with updated data

### 3. Template Rendering Engine

**Use Jinja2 for HTML templates:**
```python
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML

class TemplateRenderer:
    def __init__(self):
        self.env = Environment(loader=FileSystemLoader('templates'))
    
    def render_to_html(self, template_id: str, data: dict) -> str:
        template = self.get_template(template_id)
        jinja_template = self.env.from_string(template.content)
        
        # Add helper functions
        self.env.filters['currency'] = lambda x: f"${float(x):,.2f}"
        self.env.filters['date'] = lambda x: x.strftime('%B %d, %Y')
        
        return jinja_template.render(**data)
    
    def render_to_pdf(self, template_id: str, data: dict) -> bytes:
        html_content = self.render_to_html(template_id, data)
        pdf = HTML(string=html_content).write_pdf()
        return pdf
```

**Example Template (3-Day Notice):**
```html
<!DOCTYPE html>
<html>
<head>
    <style>
        body { font-family: Arial; margin: 40px; }
        .header { text-align: center; font-size: 18px; font-weight: bold; }
        .content { margin-top: 30px; line-height: 1.6; }
        .amount { font-size: 20px; font-weight: bold; color: #c00; }
    </style>
</head>
<body>
    <div class="header">
        THREE-DAY NOTICE TO PAY RENT OR QUIT
    </div>
    
    <div class="content">
        <p>Date: {{ current_date|date }}</p>
        
        <p>To: {{ tenant_name }}<br>
        {{ property_name }}, Unit {{ unit_name }}</p>
        
        <p>You are hereby notified that you are indebted to us in the sum of 
        <span class="amount">{{ amount_owed|currency }}</span> for rent and charges 
        now due and owing for the period from {{ delinquent_from|date }} 
        through {{ current_date|date }}.</p>
        
        {% if tenant_portion %}
        <p>Your tenant portion due is <span class="amount">{{ tenant_portion|currency }}</span>.</p>
        {% endif %}
        
        <p>You are required to pay said sum within THREE (3) DAYS from the date 
        of service of this notice or to vacate and surrender possession of the 
        above-described premises.</p>
        
        {% if payment_instructions %}
        <p><strong>Payment Instructions:</strong><br>
        {{ payment_instructions }}</p>
        {% endif %}
        
        <p>If you fail to comply, legal proceedings will be instituted against you 
        to recover possession of the premises and any rent and other charges due.</p>
        
        <p style="margin-top: 40px;">
        _________________________________<br>
        Property Manager / Owner<br>
        Date: _____________________
        </p>
    </div>
</body>
</html>
```

",
                