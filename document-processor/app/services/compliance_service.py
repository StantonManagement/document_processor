from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..database import TemplateRepository
from ..models import StateRequirements, ComplianceValidation


class ComplianceService:
    """
    Service for managing state-specific compliance requirements.
    """
    
    # State-specific requirements for eviction notices
    STATE_RULES = {
        "CA": {
            "notice_days": 3,
            "legal_reference": "California Civil Code Section 1161",
            "required_fields": ["amount_owed", "payment_deadline", "property_address", "tenant_name"],
            "special_requirements": [
                "Must include CCP reference",
                "Must be served in person or by certified mail",
                "Must include right to cure language",
            ]
        },
        "NY": {
            "notice_days": 14,
            "legal_reference": "NY Real Property Law § 711",
            "required_fields": ["amount_owed", "payment_deadline", "property_address", "court_info", "tenant_name"],
            "special_requirements": [
                "Must include court information",
                "Must mention right to legal aid",
                "Must be served by certified mail",
            ]
        },
        "TX": {
            "notice_days": 3,
            "legal_reference": "Texas Property Code § 24.005",
            "required_fields": ["amount_owed", "payment_deadline", "property_address", "tenant_name"],
            "special_requirements": [
                "Notice of right to cure",
                "Must be delivered by specific methods (hand delivery, certified mail, or posting)",
            ]
        },
        "FL": {
            "notice_days": 3,
            "legal_reference": "Florida Statutes § 83.56",
            "required_fields": ["amount_owed", "payment_deadline", "property_address", "tenant_name"],
            "special_requirements": [
                "Must demand payment or possession",
                "Must be delivered by hand or certified mail",
            ]
        },
        "IL": {
            "notice_days": 5,
            "legal_reference": "Illinois Compiled Statutes 735 ILCS 5/9-209",
            "required_fields": ["amount_owed", "payment_deadline", "property_address", "tenant_name"],
            "special_requirements": [
                "Must specify exact amount owed",
                "Must be served in person or by certified mail",
            ]
        },
    }
    
    def __init__(self, template_repo: Optional[TemplateRepository] = None):
        self.template_repo = template_repo or TemplateRepository()
    
    def get_state_requirements(self, state: str) -> Optional[StateRequirements]:
        """
        Get compliance requirements for a specific state.
        
        Args:
            state: Two-letter state code (e.g., "CA", "NY")
        
        Returns:
            StateRequirements object or None if state not found
        """
        rules = self.STATE_RULES.get(state.upper())
        if not rules:
            return None
        
        return StateRequirements(
            state=state.upper(),
            notice_days=rules["notice_days"],
            legal_reference=rules["legal_reference"],
            required_fields=rules["required_fields"],
            special_requirements=rules["special_requirements"],
        )
    
    def list_all_state_requirements(self) -> List[StateRequirements]:
        """
        Get compliance requirements for all supported states.
        
        Returns:
            List of StateRequirements objects
        """
        return [
            StateRequirements(
                state=state,
                notice_days=rules["notice_days"],
                legal_reference=rules["legal_reference"],
                required_fields=rules["required_fields"],
                special_requirements=rules["special_requirements"],
            )
            for state, rules in self.STATE_RULES.items()
        ]
    
    def get_template_for_state(
        self,
        template_type: str,
        state: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Get the correct template variant based on state.
        
        Falls back to generic template if state-specific template not found.
        
        Args:
            template_type: Type of template (e.g., "payment_notice")
            state: Two-letter state code
        
        Returns:
            Template dictionary or None if not found
        """
        # Try to get state-specific template
        templates = self.template_repo.list_templates(
            template_type=template_type,
            state=state.upper(),
            active_only=True,
        )
        
        if templates:
            # Return the latest version
            return templates[0]
        
        # Fallback to generic template (state=None)
        generic_templates = self.template_repo.list_templates(
            template_type=template_type,
            state=None,
            active_only=True,
        )
        
        if generic_templates:
            return generic_templates[0]
        
        return None
    
    def validate_compliance(
        self,
        template_type: str,
        state: str,
        data: Dict[str, Any],
    ) -> ComplianceValidation:
        """
        Validate that document data meets state requirements.
        
        Args:
            template_type: Type of template
            state: Two-letter state code
            data: Document data to validate
        
        Returns:
            ComplianceValidation with compliance status and issues
        """
        rules = self.STATE_RULES.get(state.upper())
        
        if not rules:
            # No specific rules for this state
            return ComplianceValidation(
                compliant=True,
                issues=[],
                legal_reference=None,
                special_requirements=[],
            )
        
        issues = []
        
        # Check required fields
        for required_field in rules.get("required_fields", []):
            if required_field not in data or not data[required_field]:
                issues.append(f"Missing required field: {required_field}")
        
        # Additional validation for specific fields
        if "amount_owed" in data:
            try:
                amount = float(str(data["amount_owed"]).replace("$", "").replace(",", ""))
                if amount <= 0:
                    issues.append("Amount owed must be greater than zero")
            except (ValueError, TypeError):
                issues.append("Amount owed must be a valid number")
        
        if "payment_deadline" in data:
            # In production, validate that deadline is appropriate number of days
            # based on state requirements
            pass
        
        return ComplianceValidation(
            compliant=len(issues) == 0,
            issues=issues,
            legal_reference=rules.get("legal_reference"),
            special_requirements=rules.get("special_requirements", []),
        )
    
    def get_recommended_template(
        self,
        template_type: str,
        state: Optional[str] = None,
        category: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Get recommended template based on type, state, and category.
        
        Prioritizes state-specific templates over generic ones.
        
        Args:
            template_type: Type of template
            state: Optional state code
            category: Optional category filter
        
        Returns:
            Recommended template or None
        """
        if state:
            # Try state-specific first
            template = self.get_template_for_state(template_type, state)
            if template:
                return template
        
        # Fall back to generic template
        templates = self.template_repo.list_templates(
            template_type=template_type,
            category=category,
            state=None,
            active_only=True,
        )
        
        if templates:
            return templates[0]
        
        return None
    
    def validate_template_compliance(
        self,
        template_id: str,
        state: Optional[str] = None,
    ) -> ComplianceValidation:
        """
        Validate that a template meets compliance requirements.
        
        Args:
            template_id: Template ID
            state: Optional state code to validate against
        
        Returns:
            ComplianceValidation with compliance status
        """
        template = self.template_repo.get_template(template_id)
        
        if not template:
            return ComplianceValidation(
                compliant=False,
                issues=["Template not found"],
                legal_reference=None,
                special_requirements=[],
            )
        
        # If template has a state, validate against that state's rules
        template_state = template.get("state") or state
        
        if not template_state:
            # Generic template, no specific compliance requirements
            return ComplianceValidation(
                compliant=True,
                issues=[],
                legal_reference=None,
                special_requirements=[],
            )
        
        rules = self.STATE_RULES.get(template_state.upper())
        
        if not rules:
            return ComplianceValidation(
                compliant=True,
                issues=[],
                legal_reference=None,
                special_requirements=[],
            )
        
        issues = []
        
        # Check if template includes legal reference in compliance notes
        if template.get("legal_compliance_notes"):
            if rules["legal_reference"] not in template["legal_compliance_notes"]:
                issues.append(f"Template should reference {rules['legal_reference']}")
        else:
            issues.append("Template missing legal compliance notes")
        
        return ComplianceValidation(
            compliant=len(issues) == 0,
            issues=issues,
            legal_reference=rules.get("legal_reference"),
            special_requirements=rules.get("special_requirements", []),
        )

