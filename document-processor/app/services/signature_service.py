from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta

from ..database import GeneratedDocumentRepository
from ..models import SignatureRecipient


class MockPDFFillerService:
    """
    Mock PDFfiller API service for testing.
    In production, this would integrate with the actual PDFfiller API.
    """
    
    def __init__(self):
        # In production, initialize with:
        # self.client_id = os.getenv("PDFFILLER_CLIENT_ID")
        # self.client_secret = os.getenv("PDFFILLER_CLIENT_SECRET")
        # self.api_url = os.getenv("PDFFILLER_API_URL", "https://api.pdffiller.com/v2")
        
        # Mock storage for signature requests
        self.signature_requests: Dict[str, Dict[str, Any]] = {}
    
    def create_signature_request(
        self,
        document_bytes: bytes,
        filename: str,
        recipients: List[SignatureRecipient],
        document_id: str,
    ) -> Dict[str, Any]:
        """
        Create a signature request.
        
        In production, this would:
        1. Upload document to PDFfiller
        2. Create signature request with recipients
        3. Send email notifications to recipients
        
        Args:
            document_bytes: PDF document content
            filename: Document filename
            recipients: List of signature recipients
            document_id: Internal document ID
        
        Returns:
            Dictionary with signature request details
        """
        # Generate mock signature request ID
        request_id = f"mock_sig_{uuid.uuid4().hex[:12]}"
        
        # Create mock signature request
        request_data = {
            "id": request_id,
            "document_id": document_id,
            "filename": filename,
            "status": "pending",
            "recipients": [
                {
                    "email": r.email,
                    "name": r.name,
                    "role": r.role,
                    "status": "pending",
                    "signed_at": None,
                }
                for r in recipients
            ],
            "created_at": datetime.now().isoformat(),
            "expires_at": (datetime.now() + timedelta(days=30)).isoformat(),
        }
        
        # Store in mock storage
        self.signature_requests[request_id] = request_data
        
        return {
            "signature_request_id": request_id,
            "status": "pending",
            "envelope_url": f"https://mock.pdffiller.com/sign/{request_id}",
            "recipients": request_data["recipients"],
        }
    
    def get_signature_status(self, signature_request_id: str) -> Dict[str, Any]:
        """
        Get status of a signature request.
        
        In production, this would query the PDFfiller API.
        
        Args:
            signature_request_id: Signature request ID
        
        Returns:
            Dictionary with current status
        """
        request_data = self.signature_requests.get(signature_request_id)
        
        if not request_data:
            return {
                "status": "not_found",
                "error": "Signature request not found",
            }
        
        return {
            "signature_request_id": signature_request_id,
            "status": request_data["status"],
            "recipients": request_data["recipients"],
            "created_at": request_data["created_at"],
            "expires_at": request_data["expires_at"],
        }
    
    def mock_complete_signature(
        self,
        signature_request_id: str,
        recipient_email: str,
    ) -> bool:
        """
        Mock method to simulate a recipient signing the document.
        This is for testing purposes only.
        
        Args:
            signature_request_id: Signature request ID
            recipient_email: Email of recipient who signed
        
        Returns:
            True if successful
        """
        request_data = self.signature_requests.get(signature_request_id)
        
        if not request_data:
            return False
        
        # Update recipient status
        for recipient in request_data["recipients"]:
            if recipient["email"] == recipient_email:
                recipient["status"] = "signed"
                recipient["signed_at"] = datetime.now().isoformat()
        
        # Check if all recipients have signed
        all_signed = all(r["status"] == "signed" for r in request_data["recipients"])
        
        if all_signed:
            request_data["status"] = "completed"
        
        return True


class SignatureService:
    """
    Service for managing document signatures.
    """
    
    def __init__(
        self,
        pdffiller: Optional[MockPDFFillerService] = None,
        doc_repo: Optional[GeneratedDocumentRepository] = None,
    ):
        self.pdffiller = pdffiller or MockPDFFillerService()
        self.doc_repo = doc_repo or GeneratedDocumentRepository()
    
    def send_for_signature(
        self,
        document_id: str,
        document_bytes: bytes,
        recipients: List[SignatureRecipient],
    ) -> Dict[str, Any]:
        """
        Send a document for signature.
        
        Args:
            document_id: Document ID
            document_bytes: PDF document content
            recipients: List of signature recipients
        
        Returns:
            Dictionary with signature request details
        """
        # Get document metadata
        doc = self.doc_repo.get_document(document_id)
        if not doc:
            raise ValueError("Document not found")
        
        if not doc['requires_signature']:
            raise ValueError("Document does not require signature")
        
        # Create signature request
        result = self.pdffiller.create_signature_request(
            document_bytes=document_bytes,
            filename=doc['filename'],
            recipients=recipients,
            document_id=document_id,
        )
        
        # Update document with signature request ID
        self.doc_repo.update_signature_status(
            document_id=document_id,
            signature_status="pending",
            signature_request_id=result["signature_request_id"],
        )
        
        return {
            "document_id": document_id,
            "signature_request_id": result["signature_request_id"],
            "status": "pending",
            "envelope_url": result["envelope_url"],
            "recipients": result["recipients"],
        }
    
    def get_signature_status(self, document_id: str) -> Dict[str, Any]:
        """
        Get signature status for a document.
        
        Args:
            document_id: Document ID
        
        Returns:
            Dictionary with signature status
        """
        # Get document
        doc = self.doc_repo.get_document(document_id)
        if not doc:
            raise ValueError("Document not found")
        
        if not doc['requires_signature']:
            return {
                "document_id": document_id,
                "signature_status": "not_required",
            }
        
        signature_request_id = doc.get('signature_request_id')
        if not signature_request_id:
            return {
                "document_id": document_id,
                "signature_status": doc['signature_status'],
                "error": "No signature request found",
            }
        
        # Get status from PDFfiller
        status = self.pdffiller.get_signature_status(signature_request_id)
        
        return {
            "document_id": document_id,
            "signature_status": doc['signature_status'],
            "signature_request_id": signature_request_id,
            "signed_at": doc.get('signed_at'),
            "recipients_status": status.get("recipients", []),
        }
    
    def handle_webhook(self, webhook_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle webhook from PDFfiller when signature status changes.
        
        In production, this would:
        1. Verify webhook signature
        2. Update document status
        3. Download signed document if completed
        4. Trigger any follow-up workflows
        
        Args:
            webhook_data: Webhook payload from PDFfiller
        
        Returns:
            Processing result
        """
        # Extract data from webhook
        signature_request_id = webhook_data.get("signature_request_id")
        status = webhook_data.get("status")
        document_id = webhook_data.get("document_id")
        
        if not all([signature_request_id, status, document_id]):
            raise ValueError("Invalid webhook data")
        
        # Update document status
        update_params = {
            "signature_status": status,
        }
        
        if status == "completed":
            update_params["signed_at"] = datetime.now().isoformat()
            # In production, download signed document from PDFfiller
            # and update signed_document_key
        
        self.doc_repo.update_signature_status(
            document_id=document_id,
            **update_params
        )
        
        return {
            "success": True,
            "document_id": document_id,
            "status": status,
        }

