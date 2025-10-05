from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from ..models import (
    TemplateCreate,
    TemplateResponse,
    TemplateUpdate,
    TemplateTestRender,
)
from ..services.template_service import TemplateService


router = APIRouter(prefix="/templates", tags=["templates"])


def get_template_service() -> TemplateService:
    """Dependency to get template service"""
    return TemplateService()


@router.post("", response_model=Dict[str, Any])
async def create_template(
    template: TemplateCreate,
    service: TemplateService = Depends(get_template_service),
) -> Dict[str, Any]:
    """
    Create a new document template.
    
    - **template_type**: Type identifier (e.g., "payment_notice", "work_order")
    - **name**: Human-readable name
    - **category**: collections, maintenance, or leasing
    - **state**: Optional state code for state-specific templates (e.g., "CA", "NY")
    - **template_content**: HTML/Jinja2 template content
    - **variables**: List of template variables with types and requirements
    - **requires_signature**: Whether documents generated from this template need signatures
    """
    try:
        result = service.create_template(
            template_type=template.template_type,
            name=template.name,
            category=template.category,
            template_content=template.template_content,
            variables=template.variables,
            state=template.state,
            requires_signature=template.requires_signature,
            legal_compliance_notes=template.legal_compliance_notes,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create template: {e}")


@router.get("", response_model=List[Dict[str, Any]])
async def list_templates(
    category: Optional[str] = Query(None, description="Filter by category"),
    state: Optional[str] = Query(None, description="Filter by state"),
    template_type: Optional[str] = Query(None, description="Filter by template type"),
    active_only: bool = Query(True, description="Only return active templates"),
    service: TemplateService = Depends(get_template_service),
) -> List[Dict[str, Any]]:
    """
    List all templates with optional filters.
    
    Query parameters:
    - **category**: Filter by category (collections, maintenance, leasing)
    - **state**: Filter by state code
    - **template_type**: Filter by template type
    - **active_only**: Only return active templates (default: true)
    """
    try:
        templates = service.list_templates(
            category=category,
            state=state,
            template_type=template_type,
            active_only=active_only,
        )
        return templates
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list templates: {e}")


@router.get("/{template_id}", response_model=Dict[str, Any])
async def get_template(
    template_id: str,
    service: TemplateService = Depends(get_template_service),
) -> Dict[str, Any]:
    """
    Get a specific template by ID.
    
    Returns full template details including content and variables.
    """
    template = service.get_template(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    return template


@router.patch("/{template_id}")
async def update_template(
    template_id: str,
    update: TemplateUpdate,
    service: TemplateService = Depends(get_template_service),
) -> Dict[str, str]:
    """
    Update a template.
    
    This creates a new version of the template. Only provided fields will be updated.
    
    - **name**: Update template name
    - **template_content**: Update template HTML/Jinja2 content
    - **variables**: Update variable definitions
    - **legal_compliance_notes**: Update compliance notes
    - **status**: Change status (active, deprecated, archived)
    """
    # Check if template exists
    existing = service.get_template(template_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Template not found")
    
    try:
        # Build update dict from non-None fields
        update_data = {}
        if update.name is not None:
            update_data['name'] = update.name
        if update.template_content is not None:
            update_data['template_content'] = update.template_content
        if update.variables is not None:
            update_data['variables'] = update.variables
        if update.legal_compliance_notes is not None:
            update_data['legal_compliance_notes'] = update.legal_compliance_notes
        if update.status is not None:
            update_data['status'] = update.status
        
        if not update_data:
            raise HTTPException(status_code=400, detail="No fields to update")
        
        service.update_template(template_id, **update_data)
        
        return {
            "message": "Template updated successfully",
            "template_id": template_id,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update template: {e}")


@router.post("/{template_id}/test-render")
async def test_render_template(
    template_id: str,
    test_data: TemplateTestRender,
    service: TemplateService = Depends(get_template_service),
) -> Dict[str, Any]:
    """
    Test render a template with sample data.
    
    This endpoint allows you to test template rendering without creating a document.
    Returns the rendered HTML and any validation errors or warnings.
    
    Request body:
    - **data**: Dictionary of variable values to render with
    """
    # Check if template exists
    template = service.get_template(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    try:
        rendered_html, errors = service.test_render(template_id, test_data.data)
        
        return {
            "template_id": template_id,
            "rendered_html": rendered_html,
            "validation_errors": errors,
            "success": len(errors) == 0,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to render template: {e}")

