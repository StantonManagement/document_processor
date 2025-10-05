from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

try:
    from weasyprint import CSS, HTML

    WEASYPRINT_AVAILABLE = True
except (ImportError, OSError):
    # WeasyPrint not available (missing package or system libraries)
    WEASYPRINT_AVAILABLE = False
    HTML = None
    CSS = None

from ..database import GeneratedDocumentRepository, TemplateRepository
from ..models import TemplateVariable
from .storage_service import DocumentStorageService
from .template_service import TemplateService


class GenerationService:
    """Service for generating documents from templates"""

    def __init__(
        self,
        template_service: Optional[TemplateService] = None,
        storage_service: Optional[DocumentStorageService] = None,
        template_repo: Optional[TemplateRepository] = None,
        doc_repo: Optional[GeneratedDocumentRepository] = None,
    ):
        self.template_service = template_service or TemplateService()
        self.storage_service = storage_service or DocumentStorageService()
        self.template_repo = template_repo or TemplateRepository()
        self.doc_repo = doc_repo or GeneratedDocumentRepository()

    def _add_default_styles(self, html_content: str) -> str:
        """Add default CSS styles if not present"""
        if "<style>" not in html_content and "<link" not in html_content:
            default_css = """
            <style>
                @page {
                    size: letter;
                    margin: 1in;
                }
                body {
                    font-family: Arial, Helvetica, sans-serif;
                    font-size: 12pt;
                    line-height: 1.6;
                    color: #333;
                }
                h1, h2, h3 {
                    color: #000;
                }
                .header {
                    text-align: center;
                    margin-bottom: 30px;
                }
                .signature-line {
                    margin-top: 50px;
                    border-top: 1px solid #000;
                    width: 300px;
                }
            </style>
            """
            # Insert before </head> or at the beginning
            if "</head>" in html_content:
                html_content = html_content.replace("</head>", f"{default_css}</head>")
            elif "<body>" in html_content:
                html_content = html_content.replace(
                    "<body>", f"<head>{default_css}</head><body>"
                )
            else:
                html_content = f"<html><head>{default_css}</head><body>{html_content}</body></html>"

        return html_content

    def render_to_html(
        self,
        template_id: str,
        data: Dict[str, Any],
    ) -> Tuple[str, list[str]]:
        """
        Render template to HTML.

        Args:
            template_id: Template ID
            data: Data to render with

        Returns:
            Tuple of (rendered HTML, list of validation errors)
        """
        # Get template
        template = self.template_service.get_template(template_id)
        if not template:
            raise ValueError("Template not found")

        # Add current date if not provided
        if "current_date" not in data:
            data["current_date"] = datetime.now()

        # Validate and render
        rendered, errors = self.template_service.test_render(template_id, data)

        # Add default styles
        if rendered:
            rendered = self._add_default_styles(rendered)

        return rendered, errors

    def render_to_pdf(
        self,
        template_id: str,
        data: Dict[str, Any],
    ) -> Tuple[bytes, list[str]]:
        """
        Render template to PDF.

        Args:
            template_id: Template ID
            data: Data to render with

        Returns:
            Tuple of (PDF bytes, list of validation errors)
        """
        if not WEASYPRINT_AVAILABLE:
            raise RuntimeError(
                "WeasyPrint is not available. Install it with: pip install weasyprint"
            )

        # Render to HTML first
        html_content, errors = self.render_to_html(template_id, data)

        if not html_content:
            raise ValueError("Failed to render HTML template")

        # Convert HTML to PDF
        try:
            pdf_bytes = HTML(string=html_content).write_pdf()
            return pdf_bytes, errors
        except Exception as e:
            errors.append(f"PDF generation error: {e}")
            raise ValueError(f"PDF generation failed: {e}")

    def generate_document(
        self,
        template_id: str,
        data: Dict[str, Any],
        output_format: str = "pdf",
        metadata: Optional[Dict[str, Any]] = None,
        requires_signature: bool = False,
        created_by: str = "system",
    ) -> Dict[str, Any]:
        """
        Generate a document from a template.

        Args:
            template_id: Template ID
            data: Data to render with
            output_format: Output format (pdf or html)
            metadata: Additional metadata
            requires_signature: Whether document requires signature
            created_by: User who created the document

        Returns:
            Dictionary with document_id, status, document_url, etc.
        """
        # Get template info
        template = self.template_service.get_template(template_id)
        if not template:
            raise ValueError("Template not found")

        # Generate document content
        if output_format == "pdf":
            content_bytes, errors = self.render_to_pdf(template_id, data)
            file_extension = "pdf"
        elif output_format == "html":
            html_content, errors = self.render_to_html(template_id, data)
            content_bytes = html_content.encode("utf-8")
            file_extension = "html"
        else:
            raise ValueError(f"Unsupported output format: {output_format}")

        if errors:
            # Log warnings but continue if we have content
            print(f"Warnings during generation: {errors}")

        # Generate filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{template['template_type']}_{timestamp}.{file_extension}"

        # Prepare metadata
        full_metadata = metadata or {}
        full_metadata.update(
            {
                "template_id": template_id,
                "template_type": template["template_type"],
                "template_name": template["name"],
                "generated_at": datetime.now().isoformat(),
                "output_format": output_format,
            }
        )

        # Create document record
        doc_record = self.doc_repo.create_document(
            filename=filename,
            storage_key="",  # Will be updated after storage
            category=template["category"],
            created_by=created_by,
            template_id=template_id,
            template_type=template["template_type"],
            tenant_id=full_metadata.get("tenant_id"),
            property_id=full_metadata.get("property_id"),
            unit_id=full_metadata.get("unit_id"),
            workflow_id=full_metadata.get("workflow_id"),
            requires_signature=requires_signature,
            file_size=len(content_bytes),
            metadata=full_metadata,
        )

        document_id = doc_record["id"]

        # Store document
        document_url = self.storage_service.store_document(
            document_id=document_id,
            document_bytes=content_bytes,
            filename=filename,
            category=template["category"],
            metadata=full_metadata,
        )

        # Update storage key in database
        storage_key = f"documents/{template['category']}/{document_id}/{filename}"
        self.doc_repo.update_storage_key(document_id, storage_key)

        return {
            "document_id": document_id,
            "status": "generated",
            "document_url": document_url,
            "signature_status": doc_record["signature_status"],
            "signature_envelope_id": None,  # Set when signature is requested
            "created_at": doc_record["created_at"],
        }

    def regenerate_document(
        self,
        document_id: str,
        data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Regenerate an existing document with new data.

        Args:
            document_id: Existing document ID
            data: New data to render with

        Returns:
            Updated document information
        """
        # Get existing document
        doc = self.doc_repo.get_document(document_id)
        if not doc:
            raise ValueError("Document not found")

        # Get template
        template_id = doc["template_id"]
        if not template_id:
            raise ValueError("Document has no associated template")

        # Generate new document with same settings
        metadata = doc.get("metadata", {})

        # Determine output format from original filename
        filename = doc.get("filename", "")
        output_format = "pdf" if filename.endswith(".pdf") else "html"

        return self.generate_document(
            template_id=template_id,
            data=data,
            output_format=output_format,
            metadata=metadata,
            requires_signature=doc["requires_signature"],
            created_by=doc["created_by"],
        )
