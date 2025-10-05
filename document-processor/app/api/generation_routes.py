from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from ..database import GeneratedDocumentRepository
from ..models import DocumentGenerateRequest, DocumentGenerateResponse
from ..services.generation_service import GenerationService
from ..services.storage_service import DocumentStorageService


router = APIRouter(prefix="/documents", tags=["document-generation"])


def get_generation_service() -> GenerationService:
    """Dependency to get generation service"""
    return GenerationService()


def get_generated_doc_repo() -> GeneratedDocumentRepository:
    """Dependency to get generated document repository"""
    return GeneratedDocumentRepository()


def get_storage_service() -> DocumentStorageService:
    """Dependency to get storage service"""
    return DocumentStorageService()


@router.post("/generate", response_model=DocumentGenerateResponse)
async def generate_document(
    request: DocumentGenerateRequest,
    service: GenerationService = Depends(get_generation_service),
) -> DocumentGenerateResponse:
    """
    Generate a document from a template.
    
    - **template_id**: ID of the template to use
    - **data**: Dictionary of variable values for template rendering
    - **output_format**: Output format (pdf or html), default is pdf
    - **metadata**: Optional metadata (tenant_id, property_id, workflow_id, etc.)
    - **requires_signature**: Whether the document requires signatures
    - **signature_recipients**: List of recipients if signature is required
    
    Returns:
    - **document_id**: Generated document ID
    - **status**: Generation status
    - **document_url**: URL to download the document
    - **signature_status**: Signature status if applicable
    """
    try:
        result = service.generate_document(
            template_id=request.template_id,
            data=request.data,
            output_format=request.output_format,
            metadata=request.metadata,
            requires_signature=request.requires_signature,
            created_by=request.metadata.get('created_by', 'system') if request.metadata else 'system',
        )
        
        return DocumentGenerateResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate document: {e}")


@router.get("/{document_id}/metadata")
async def get_document_metadata(
    document_id: str,
    repo: GeneratedDocumentRepository = Depends(get_generated_doc_repo),
) -> Dict[str, Any]:
    """
    Get metadata for a generated document.
    
    Returns document information including:
    - File details (name, size, type)
    - Template information
    - Signature status
    - Associated entities (tenant, property, etc.)
    - Timestamps
    """
    doc = repo.get_document(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    return {
        "document_id": doc['id'],
        "filename": doc['filename'],
        "template_id": doc.get('template_id'),
        "template_type": doc.get('template_type'),
        "category": doc['category'],
        "tenant_id": doc.get('tenant_id'),
        "property_id": doc.get('property_id'),
        "unit_id": doc.get('unit_id'),
        "created_by": doc['created_by'],
        "workflow_id": doc.get('workflow_id'),
        "requires_signature": doc['requires_signature'],
        "signature_status": doc.get('signature_status'),
        "file_size": doc.get('file_size'),
        "metadata": doc.get('metadata', {}),
        "created_at": doc['created_at'],
        "updated_at": doc['updated_at'],
    }


@router.get("/{document_id}/download")
async def download_document(
    document_id: str,
    repo: GeneratedDocumentRepository = Depends(get_generated_doc_repo),
    storage: DocumentStorageService = Depends(get_storage_service),
) -> StreamingResponse:
    """
    Download a generated document.
    
    Returns the document file as a streaming response.
    Logs the access for audit purposes.
    """
    # Get document metadata
    doc = repo.get_document(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Get file from storage
    storage_key = doc['storage_key']
    file_bytes = storage.get_document_bytes(storage_key)
    
    if not file_bytes:
        raise HTTPException(status_code=404, detail="Document file not found in storage")
    
    # Log access
    repo.log_access(
        document_id=document_id,
        accessed_by="system",  # In production, get from auth context
        access_type="download",
    )
    
    # Determine content type
    filename = doc['filename']
    if filename.endswith('.pdf'):
        media_type = 'application/pdf'
    elif filename.endswith('.html'):
        media_type = 'text/html'
    else:
        media_type = 'application/octet-stream'
    
    # Return as streaming response
    import io
    return StreamingResponse(
        io.BytesIO(file_bytes),
        media_type=media_type,
        headers={
            'Content-Disposition': f'attachment; filename="{filename}"'
        }
    )


@router.post("/{document_id}/regenerate", response_model=DocumentGenerateResponse)
async def regenerate_document(
    document_id: str,
    data: Dict[str, Any],
    service: GenerationService = Depends(get_generation_service),
    repo: GeneratedDocumentRepository = Depends(get_generated_doc_repo),
) -> DocumentGenerateResponse:
    """
    Regenerate an existing document with new data.
    
    This creates a new document using the same template but with updated data.
    The original document is not modified.
    
    - **data**: New variable values for template rendering
    
    Returns a new document with a new document_id.
    """
    # Check if document exists
    doc = repo.get_document(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    try:
        result = service.regenerate_document(
            document_id=document_id,
            data=data,
        )
        
        return DocumentGenerateResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to regenerate document: {e}")

