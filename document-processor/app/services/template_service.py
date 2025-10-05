from __future__ import annotations

import json
from typing import Any, Dict, Optional

from jinja2 import (
    Environment,
    StrictUndefined,
    Template,
    TemplateSyntaxError,
    UndefinedError,
)

from ..database import TemplateRepository
from ..models import TemplateVariable


class TemplateService:
    def __init__(self, repo: Optional[TemplateRepository] = None):
        self.repo = repo or TemplateRepository()
        self.env = Environment(autoescape=True, undefined=StrictUndefined)

        # Add custom filters
        self.env.filters["currency"] = self._currency_filter
        self.env.filters["date"] = self._date_filter
        self.env.filters["phone"] = self._phone_filter

    def _currency_filter(self, value: Any) -> str:
        """Format value as currency"""
        try:
            return f"${float(value):,.2f}"
        except (ValueError, TypeError):
            return str(value)

    def _date_filter(self, value: Any, format: str = "%B %d, %Y") -> str:
        """Format date value"""
        from datetime import datetime

        if isinstance(value, str):
            # Try to parse common date formats
            for fmt in ["%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%Y-%m-%dT%H:%M:%S"]:
                try:
                    value = datetime.strptime(value, fmt)
                    break
                except ValueError:
                    continue

        if isinstance(value, datetime):
            return value.strftime(format)

        return str(value)

    def _phone_filter(self, value: Any) -> str:
        """Format phone number"""
        digits = "".join(filter(str.isdigit, str(value)))
        if len(digits) == 10:
            return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
        return str(value)

    def validate_template(self, template_content: str) -> tuple[bool, Optional[str]]:
        """Validate Jinja2 template syntax"""
        try:
            self.env.from_string(template_content)
            return True, None
        except TemplateSyntaxError as e:
            return False, f"Template syntax error: {e}"
        except Exception as e:
            return False, f"Template validation error: {e}"

    def validate_variables(
        self, variables: list[TemplateVariable], data: Dict[str, Any]
    ) -> tuple[bool, list[str]]:
        """Validate that required variables are present in data"""
        errors = []

        for var in variables:
            if var.required and var.name not in data:
                errors.append(f"Missing required variable: {var.name}")

            # Type validation
            if var.name in data:
                value = data[var.name]
                if var.type == "number" and not isinstance(value, (int, float)):
                    try:
                        float(value)
                    except (ValueError, TypeError):
                        errors.append(f"Variable '{var.name}' must be a number")
                elif var.type == "boolean" and not isinstance(value, bool):
                    errors.append(f"Variable '{var.name}' must be a boolean")
                elif var.type == "array" and not isinstance(value, list):
                    errors.append(f"Variable '{var.name}' must be an array")
                elif var.type == "object" and not isinstance(value, dict):
                    errors.append(f"Variable '{var.name}' must be an object")

        return len(errors) == 0, errors

    def render_template(self, template_content: str, data: Dict[str, Any]) -> str:
        """Render Jinja2 template with data"""
        try:
            template = self.env.from_string(template_content)
            return template.render(**data)
        except UndefinedError as e:
            raise ValueError(f"Template rendering error - undefined variable: {e}")
        except Exception as e:
            raise ValueError(f"Template rendering error: {e}")

    def create_template(
        self,
        template_type: str,
        name: str,
        category: str,
        template_content: str,
        variables: list[TemplateVariable],
        state: Optional[str] = None,
        requires_signature: bool = False,
        legal_compliance_notes: Optional[str] = None,
        created_by: str = "system",
    ) -> Dict[str, Any]:
        """Create a new template"""
        # Validate template syntax
        is_valid, error = self.validate_template(template_content)
        if not is_valid:
            raise ValueError(error)

        # Serialize variables to JSON
        variables_json = json.dumps([v.model_dump() for v in variables])

        return self.repo.create_template(
            template_type=template_type,
            name=name,
            category=category,
            template_content=template_content,
            variables=variables_json,
            state=state,
            requires_signature=requires_signature,
            legal_compliance_notes=legal_compliance_notes,
            created_by=created_by,
        )

    def get_template(self, template_id: str) -> Optional[Dict[str, Any]]:
        """Get template by ID"""
        template = self.repo.get_template(template_id)
        if template and template.get("variables"):
            # Parse variables JSON
            try:
                template["variables"] = json.loads(template["variables"])
            except Exception:
                template["variables"] = []
        return template

    def list_templates(
        self,
        category: Optional[str] = None,
        state: Optional[str] = None,
        template_type: Optional[str] = None,
        active_only: bool = True,
    ) -> list[Dict[str, Any]]:
        """List templates with optional filters"""
        templates = self.repo.list_templates(
            category=category,
            state=state,
            template_type=template_type,
            active_only=active_only,
        )

        # Parse variables JSON for each template
        for template in templates:
            if template.get("variables"):
                try:
                    template["variables"] = json.loads(template["variables"])
                except Exception:
                    template["variables"] = []

        return templates

    def update_template(self, template_id: str, **kwargs) -> None:
        """Update template fields"""
        # If template_content is being updated, validate it
        if "template_content" in kwargs:
            is_valid, error = self.validate_template(kwargs["template_content"])
            if not is_valid:
                raise ValueError(error)

        # If variables are being updated, serialize them
        if "variables" in kwargs and isinstance(kwargs["variables"], list):
            kwargs["variables"] = json.dumps(
                [
                    v.model_dump() if isinstance(v, TemplateVariable) else v
                    for v in kwargs["variables"]
                ]
            )

        self.repo.update_template(template_id, **kwargs)

    def test_render(
        self, template_id: str, data: Dict[str, Any]
    ) -> tuple[str, list[str]]:
        """Test render a template with sample data"""
        template = self.get_template(template_id)
        if not template:
            raise ValueError("Template not found")

        # Parse variables
        variables = []
        if template.get("variables"):
            if isinstance(template["variables"], str):
                variables = [
                    TemplateVariable(**v) for v in json.loads(template["variables"])
                ]
            else:
                variables = [TemplateVariable(**v) for v in template["variables"]]

        # Validate variables
        is_valid, errors = self.validate_variables(variables, data)

        # Render template
        try:
            rendered = self.render_template(template["template_content"], data)
            return rendered, errors
        except Exception as e:
            errors.append(str(e))
            return "", errors

            rendered = self.render_template(template["template_content"], data)
            return rendered, errors
        except Exception as e:
            errors.append(str(e))
            return "", errors

            rendered = self.render_template(template["template_content"], data)
            return rendered, errors
        except Exception as e:
            errors.append(str(e))
            return "", errors
