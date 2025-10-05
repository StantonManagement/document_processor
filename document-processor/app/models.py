from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class DocumentUpload(BaseModel):
    file_name: str
    file_type: Literal["pdf", "png", "jpg", "docx"]
    file_size: int
    uploaded_by: Optional[str] = "system"


class DocumentStatus(BaseModel):
    document_id: str
    status: Literal["pending", "processing", "completed", "failed"]
    created_at: datetime
    updated_at: datetime
    error_message: Optional[str] = None


class ExtractedContent(BaseModel):
    document_id: str
    raw_text: str
    confidence_score: float = Field(ge=0.0, le=1.0)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    pages: Optional[int] = None
    language: Optional[str] = "en"


class ParsedData(BaseModel):
    document_type: str
    fields: Dict[str, Any]
    validation_errors: List[str] = Field(default_factory=list)
    parsing_confidence: float = Field(ge=0.0, le=1.0)


# Template Management Models
class TemplateVariable(BaseModel):
    name: str
    type: Literal["string", "number", "currency", "date", "boolean", "object", "array"]
    required: bool = True
    description: Optional[str] = None
    default: Optional[Any] = None


class TemplateCreate(BaseModel):
    template_type: str
    name: str
    category: Literal["collections", "maintenance", "leasing"]
    state: Optional[str] = None
    template_content: str  # HTML/Jinja2 template
    variables: List[TemplateVariable]
    requires_signature: bool = False
    legal_compliance_notes: Optional[str] = None


class TemplateResponse(BaseModel):
    id: str
    template_type: str
    name: str
    category: str
    state: Optional[str] = None
    version: int
    template_content: str
    variables: List[TemplateVariable]
    requires_signature: bool
    legal_compliance_notes: Optional[str] = None
    status: str
    created_by: Optional[str] = None
    created_at: str
    updated_at: str


class TemplateUpdate(BaseModel):
    name: Optional[str] = None
    template_content: Optional[str] = None
    variables: Optional[List[TemplateVariable]] = None
    legal_compliance_notes: Optional[str] = None
    status: Optional[Literal["active", "deprecated", "archived"]] = None


class TemplateTestRender(BaseModel):
    data: Dict[str, Any]


# Document Generation Models
class SignatureRecipient(BaseModel):
    email: str
    name: str
    role: str


class DocumentGenerateRequest(BaseModel):
    template_id: str
    data: Dict[str, Any]
    output_format: Literal["pdf", "html"] = "pdf"
    metadata: Optional[Dict[str, Any]] = None
    requires_signature: bool = False
    signature_recipients: Optional[List[SignatureRecipient]] = None


class DocumentGenerateResponse(BaseModel):
    document_id: str
    status: str
    document_url: Optional[str] = None
    signature_status: Optional[str] = None
    signature_envelope_id: Optional[str] = None
    created_at: str


class GeneratedDocumentMetadata(BaseModel):
    document_id: str
    filename: str
    template_id: Optional[str] = None
    template_type: Optional[str] = None
    category: str
    tenant_id: Optional[int] = None
    property_id: Optional[int] = None
    unit_id: Optional[int] = None
    created_by: str
    workflow_id: Optional[str] = None
    requires_signature: bool
    signature_status: Optional[str] = None
    file_size: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None
    created_at: str
    updated_at: str


# Classification Models
class DocumentClassification(BaseModel):
    type: str
    confidence: float = Field(ge=0.0, le=1.0)
    extracted_fields: Dict[str, Any]


class ProcessAndClassifyResponse(BaseModel):
    document_id: str
    type: str
    confidence: float
    extracted_fields: Dict[str, Any]


# Compliance Models
class StateRequirements(BaseModel):
    state: str
    notice_days: int
    legal_reference: str
    required_fields: List[str]
    special_requirements: List[str]


class ComplianceValidation(BaseModel):
    compliant: bool
    issues: List[str]
    legal_reference: Optional[str] = None
    special_requirements: List[str] = Field(default_factory=list)


# Signature Models
class SignatureRequest(BaseModel):
    signature_recipients: List[SignatureRecipient]


class SignatureStatusResponse(BaseModel):
    document_id: str
    signature_status: str
    signature_request_id: Optional[str] = None
    signed_at: Optional[str] = None
    recipients_status: Optional[List[Dict[str, Any]]] = None
