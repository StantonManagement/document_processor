from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from ..models import StateRequirements, ComplianceValidation
from ..services.compliance_service import ComplianceService


router = APIRouter(prefix="/compliance", tags=["compliance"])


def get_compliance_service() -> ComplianceService:
    """Dependency to get compliance service"""
    return ComplianceService()


@router.get("/states", response_model=List[StateRequirements])
async def list_state_requirements(
    state: Optional[str] = Query(None, description="Filter by specific state code"),
    service: ComplianceService = Depends(get_compliance_service),
) -> List[StateRequirements]:
    """
    Get state-specific compliance requirements.
    
    Returns requirements for all supported states, or a specific state if provided.
    
    Each state requirement includes:
    - **notice_days**: Required notice period
    - **legal_reference**: Relevant statute or code section
    - **required_fields**: Fields that must be present in documents
    - **special_requirements**: Additional compliance notes
    """
    if state:
        requirement = service.get_state_requirements(state)
        if not requirement:
            raise HTTPException(
                status_code=404,
                detail=f"No compliance requirements found for state: {state}"
            )
        return [requirement]
    
    return service.list_all_state_requirements()


@router.post("/validate", response_model=ComplianceValidation)
async def validate_compliance(
    template_type: str,
    state: str,
    data: Dict[str, Any],
    service: ComplianceService = Depends(get_compliance_service),
) -> ComplianceValidation:
    """
    Validate that document data meets state compliance requirements.
    
    - **template_type**: Type of document (e.g., "payment_notice")
    - **state**: Two-letter state code (e.g., "CA", "NY")
    - **data**: Document data to validate
    
    Returns:
    - **compliant**: Whether the data meets all requirements
    - **issues**: List of compliance issues found
    - **legal_reference**: Relevant legal statute
    - **special_requirements**: Additional requirements to consider
    """
    try:
        validation = service.validate_compliance(
            template_type=template_type,
            state=state,
            data=data,
        )
        return validation
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Validation failed: {e}"
        )


@router.get("/template/{template_id}/validate", response_model=ComplianceValidation)
async def validate_template_compliance(
    template_id: str,
    state: Optional[str] = Query(None, description="State to validate against"),
    service: ComplianceService = Depends(get_compliance_service),
) -> ComplianceValidation:
    """
    Validate that a template meets compliance requirements.
    
    - **template_id**: Template ID to validate
    - **state**: Optional state code to validate against (uses template's state if not provided)
    
    Returns compliance validation results.
    """
    try:
        validation = service.validate_template_compliance(
            template_id=template_id,
            state=state,
        )
        return validation
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Template validation failed: {e}"
        )


@router.get("/template/recommend")
async def get_recommended_template(
    template_type: str,
    state: Optional[str] = Query(None, description="State code for state-specific template"),
    category: Optional[str] = Query(None, description="Template category"),
    service: ComplianceService = Depends(get_compliance_service),
) -> Dict[str, Any]:
    """
    Get recommended template based on type, state, and category.
    
    Prioritizes state-specific templates over generic ones.
    
    - **template_type**: Type of template needed
    - **state**: Optional state code for state-specific template
    - **category**: Optional category filter
    
    Returns the recommended template or 404 if none found.
    """
    template = service.get_recommended_template(
        template_type=template_type,
        state=state,
        category=category,
    )
    
    if not template:
        raise HTTPException(
            status_code=404,
            detail=f"No template found for type '{template_type}'"
        )
    
    return template

