from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException

from ..database import GeneratedDocumentRepository
from ..models import SignatureRequest, SignatureStatusResponse
from ..services.signature_service import SignatureService
from ..services.storage_service import DocumentStorageService


router = APIRouter(prefix="/documents", tags=["e-signature"])


def get_signature_service() -> SignatureService:
    """Dependency to get signature service"""
    return SignatureService()


def get_generated_doc_repo() -> GeneratedDocumentRepository:
    """Dependency to get generated document repository"""
    return GeneratedDocumentRepository()


def get_storage_service() -> DocumentStorageService:
    """Dependency to get storage service"""
    return DocumentStorageService()


@router.post("/{document_id}/send-for-signature")
async def send_for_signature(
    document_id: str,
    request: SignatureRequest,
    service: SignatureService = Depends(get_signature_service),
    repo: GeneratedDocumentRepository = Depends(get_generated_doc_repo),
    storage: DocumentStorageService = Depends(get_storage_service),
) -> Dict[str, Any]:
    """
    Send a document for e-signature.
    
    - **signature_recipients**: List of recipients who need to sign
    
    Returns:
    - **document_id**: Document ID
    - **signature_request_id**: Signature request ID from PDFfiller
    - **status**: Current signature status
    - **envelope_url**: URL for recipients to access and sign
    - **recipients**: List of recipients with their status
    """
    # Get document
    doc = repo.get_document(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    if not doc['requires_signature']:
        raise HTTPException(
            status_code=400,
            detail="Document does not require signature"
        )
    
    # Get document bytes from storage
    storage_key = doc['storage_key']
    document_bytes = storage.get_document_bytes(storage_key)
    
    if not document_bytes:
        raise HTTPException(
            status_code=404,
            detail="Document file not found in storage"
        )
    
    try:
        result = service.send_for_signature(
            document_id=document_id,
            document_bytes=document_bytes,
            recipients=request.signature_recipients,
        )
        
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to send document for signature: {e}"
        )


@router.get("/{document_id}/signature-status", response_model=SignatureStatusResponse)
async def get_signature_status(
    document_id: str,
    service: SignatureService = Depends(get_signature_service),
) -> SignatureStatusResponse:
    """
    Get signature status for a document.
    
    Returns:
    - **document_id**: Document ID
    - **signature_status**: Current status (not_required, pending, signed, declined, expired)
    - **signature_request_id**: Signature request ID if applicable
    - **signed_at**: Timestamp when all signatures were completed
    - **recipients_status**: Status of each recipient
    """
    try:
        status = service.get_signature_status(document_id)
        return SignatureStatusResponse(**status)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get signature status: {e}"
        )


@router.post("/webhooks/pdffiller")
async def pdffiller_webhook(
    webhook_data: Dict[str, Any],
    service: SignatureService = Depends(get_signature_service),
) -> Dict[str, str]:
    """
    Webhook handler for PDFfiller signature events.
    
    This endpoint receives notifications from PDFfiller when:
    - A recipient signs the document
    - A recipient declines to sign
    - The signature request expires
    - All signatures are completed
    
    In production, this should:
    1. Verify webhook signature for security
    2. Process the event
    3. Update document status
    4. Trigger any follow-up workflows
    """
    try:
        result = service.handle_webhook(webhook_data)
        return {
            "status": "success",
            "message": "Webhook processed successfully",
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process webhook: {e}"
        )

