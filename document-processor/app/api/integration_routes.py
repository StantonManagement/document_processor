from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
import httpx

from ..database import DocumentRepository
from ..models import ProcessAndClassifyResponse
from ..services.classification_service import ClassificationService
from ..services.queue_service import InMemoryQueueService
from ..api.dependencies import get_repo, get_queue_service


router = APIRouter(prefix="/documents", tags=["integration"])


def get_classification_service() -> ClassificationService:
    """Dependency to get classification service"""
    return ClassificationService()


@router.post("/process-and-classify", response_model=ProcessAndClassifyResponse)
async def process_and_classify(
    file: UploadFile = File(...),
    repo: DocumentRepository = Depends(get_repo),
    queue: InMemoryQueueService = Depends(get_queue_service),
    classifier: ClassificationService = Depends(get_classification_service),
) -> ProcessAndClassifyResponse:
    """
    Process an uploaded document using OCR and classify it.
    
    This endpoint combines:
    1. Document upload and OCR processing (existing functionality)
    2. AI-powered document classification
    3. Field extraction based on document type
    
    Workflow:
    1. Upload document for OCR processing
    2. Wait for text extraction to complete
    3. Classify document type using AI
    4. Extract relevant fields based on type
    
    Returns:
    - **document_id**: Processed document ID
    - **type**: Classified document type
    - **confidence**: Classification confidence (0-1)
    - **extracted_fields**: Extracted data fields
    """
    from ..utils.validators import validate_file
    import time
    
    # Validate file
    try:
        ext, size = validate_file(file)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    
    # Upload for OCR processing
    content = await file.read()
    meta = repo.create_document(file.filename or "file", ext, size)
    document_id = meta["id"]
    
    # Enqueue for background processing
    queue.start()
    queue.enqueue(document_id, ext, content)
    
    # Wait for processing to complete (with timeout)
    max_wait = 30  # seconds
    wait_interval = 0.5
    elapsed = 0
    
    while elapsed < max_wait:
        doc = repo.get_document(document_id)
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        
        if doc["status"] == "completed":
            break
        elif doc["status"] == "failed":
            raise HTTPException(
                status_code=500,
                detail=f"Document processing failed: {doc.get('error_message', 'Unknown error')}"
            )
        
        time.sleep(wait_interval)
        elapsed += wait_interval
    
    # Check if processing completed
    doc = repo.get_document(document_id)
    if doc["status"] != "completed":
        raise HTTPException(
            status_code=408,
            detail="Document processing timeout. Try checking status later."
        )
    
    # Get extracted text
    extracted_text = doc.get("raw_text", "")
    
    if not extracted_text:
        raise HTTPException(
            status_code=400,
            detail="No text could be extracted from document"
        )
    
    # Classify document
    try:
        classification = await classifier.classify_document(extracted_text)
        
        # Update document with classification results
        parsed_data = {
            "document_type": classification.type,
            "confidence": classification.confidence,
            "extracted_fields": classification.extracted_fields,
        }
        repo.update_status(
            document_id,
            "completed",
            parsed_data=parsed_data
        )
        
        return ProcessAndClassifyResponse(
            document_id=document_id,
            type=classification.type,
            confidence=classification.confidence,
            extracted_fields=classification.extracted_fields,
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Classification failed: {e}"
        )


@router.post("/process-external")
async def process_external_document(
    file: UploadFile = File(...),
    doc_processing_url: str = "http://localhost:8000",
) -> Dict[str, Any]:
    """
    Process a document using an external document processing service.
    
    This demonstrates integration with Gabriel's document processing service
    when it's running as a separate service.
    
    - **file**: Document file to process
    - **doc_processing_url**: URL of the document processing service
    
    Returns the processing result from the external service.
    """
    try:
        # Call external document processing service
        async with httpx.AsyncClient(timeout=30.0) as client:
            files = {
                "file": (
                    file.filename,
                    await file.read(),
                    file.content_type or "application/octet-stream"
                )
            }
            
            response = await client.post(
                f"{doc_processing_url}/documents/upload",
                files=files
            )
            
            if response.status_code != 200:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"External processing failed: {response.text}"
                )
            
            return response.json()
    except httpx.TimeoutException:
        raise HTTPException(
            status_code=408,
            detail="External document processing service timeout"
        )
    except httpx.RequestError as e:
        raise HTTPException(
            status_code=503,
            detail=f"External document processing service unavailable: {e}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process document: {e}"
        )

