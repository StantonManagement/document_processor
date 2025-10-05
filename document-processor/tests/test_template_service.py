import pytest
from app.models import TemplateVariable
from app.services.template_service import TemplateService


@pytest.fixture
def template_service():
    return TemplateService()


def test_currency_filter(template_service):
    """Test currency formatting filter"""
    assert template_service._currency_filter(1500) == "$1,500.00"
    assert template_service._currency_filter("1500.50") == "$1,500.50"
    assert template_service._currency_filter(0) == "$0.00"


def test_phone_filter(template_service):
    """Test phone number formatting filter"""
    assert template_service._phone_filter("5551234567") == "(555) 123-4567"
    assert template_service._phone_filter("555-123-4567") == "(555) 123-4567"


def test_validate_template_valid(template_service):
    """Test template validation with valid Jinja2 syntax"""
    template_content = "<html><body>Hello {{ name }}</body></html>"
    is_valid, error = template_service.validate_template(template_content)
    assert is_valid is True
    assert error is None


def test_validate_template_invalid(template_service):
    """Test template validation with invalid Jinja2 syntax"""
    template_content = "<html><body>Hello {{ name </body></html>"
    is_valid, error = template_service.validate_template(template_content)
    assert is_valid is False
    assert error is not None


def test_validate_variables_all_present(template_service):
    """Test variable validation when all required variables are present"""
    variables = [
        TemplateVariable(name="tenant_name", type="string", required=True),
        TemplateVariable(name="amount_owed", type="currency", required=True),
    ]
    data = {"tenant_name": "John Smith", "amount_owed": "1500.00"}
    is_valid, errors = template_service.validate_variables(variables, data)
    assert is_valid is True
    assert len(errors) == 0


def test_validate_variables_missing_required(template_service):
    """Test variable validation when required variables are missing"""
    variables = [
        TemplateVariable(name="tenant_name", type="string", required=True),
        TemplateVariable(name="amount_owed", type="currency", required=True),
    ]
    data = {"tenant_name": "John Smith"}
    is_valid, errors = template_service.validate_variables(variables, data)
    assert is_valid is False
    assert len(errors) == 1
    assert "amount_owed" in errors[0]


def test_render_template_simple(template_service):
    """Test simple template rendering"""
    template_content = "Hello {{ name }}!"
    data = {"name": "World"}
    rendered = template_service.render_template(template_content, data)
    assert rendered == "Hello World!"


def test_render_template_with_filters(template_service):
    """Test template rendering with custom filters"""
    template_content = "Amount: {{ amount|currency }}"
    data = {"amount": 1500}
    rendered = template_service.render_template(template_content, data)
    assert "$1,500.00" in rendered


def test_render_template_undefined_variable(template_service):
    """Test template rendering with undefined variable raises error"""
    template_content = "Hello {{ undefined_var }}!"
    data = {}
    with pytest.raises(ValueError, match="undefined variable"):
        template_service.render_template(template_content, data)


def test_create_template(template_service):
    """Test template creation"""
    variables = [
        TemplateVariable(name="tenant_name", type="string", required=True),
    ]

    result = template_service.create_template(
        template_type="test_template",
        name="Test Template",
        category="collections",
        template_content="<html>{{ tenant_name }}</html>",
        variables=variables,
        state="CA",
    )

    assert "id" in result
    assert result["template_type"] == "test_template"
    # Version may be > 1 if template already exists from previous test runs
    assert result["version"] >= 1
    assert result["status"] == "active"


def test_create_template_invalid_syntax(template_service):
    """Test template creation with invalid syntax raises error"""
    variables = [
        TemplateVariable(name="tenant_name", type="string", required=True),
    ]

    with pytest.raises(ValueError):
        template_service.create_template(
            template_type="test_template",
            name="Test Template",
            category="collections",
            template_content="<html>{{ tenant_name </html>",  # Invalid syntax
            variables=variables,
        )


def test_get_template(template_service):
    """Test getting a template by ID"""
    # First create a template
    variables = [
        TemplateVariable(name="test_var", type="string", required=True),
    ]

    result = template_service.create_template(
        template_type="test_get",
        name="Test Get Template",
        category="maintenance",
        template_content="<html>Test</html>",
        variables=variables,
    )

    template_id = result["id"]

    # Now get it
    template = template_service.get_template(template_id)
    assert template is not None
    assert template["id"] == template_id
    assert template["name"] == "Test Get Template"
    assert isinstance(template["variables"], list)


def test_list_templates(template_service):
    """Test listing templates with filters"""
    # Create a few templates
    variables = [TemplateVariable(name="test", type="string", required=True)]

    template_service.create_template(
        template_type="type1",
        name="Template 1",
        category="collections",
        template_content="<html>1</html>",
        variables=variables,
        state="CA",
    )

    template_service.create_template(
        template_type="type2",
        name="Template 2",
        category="maintenance",
        template_content="<html>2</html>",
        variables=variables,
        state="NY",
    )

    # List all
    all_templates = template_service.list_templates(active_only=True)
    assert len(all_templates) >= 2

    # Filter by category
    collections = template_service.list_templates(category="collections")
    assert all(t["category"] == "collections" for t in collections)

    # Filter by state
    ca_templates = template_service.list_templates(state="CA")
    assert all(t["state"] == "CA" for t in ca_templates)


def test_update_template(template_service):
    """Test updating a template"""
    variables = [TemplateVariable(name="test", type="string", required=True)]

    result = template_service.create_template(
        template_type="test_update",
        name="Original Name",
        category="leasing",
        template_content="<html>Original</html>",
        variables=variables,
    )

    template_id = result["id"]

    # Update the template
    template_service.update_template(
        template_id, name="Updated Name", status="deprecated"
    )

    # Verify update
    updated = template_service.get_template(template_id)
    assert updated["name"] == "Updated Name"
    assert updated["status"] == "deprecated"


def test_test_render(template_service):
    """Test the test_render functionality"""
    variables = [
        TemplateVariable(name="name", type="string", required=True),
        TemplateVariable(name="amount", type="currency", required=True),
    ]

    result = template_service.create_template(
        template_type="test_render",
        name="Test Render Template",
        category="collections",
        template_content="<html>Hello {{ name }}, you owe {{ amount|currency }}</html>",
        variables=variables,
    )

    template_id = result["id"]

    # Test render with valid data
    rendered, errors = template_service.test_render(
        template_id, {"name": "John", "amount": 1500}
    )

    assert "Hello John" in rendered
    assert "$1,500.00" in rendered
    assert len(errors) == 0


def test_test_render_missing_required(template_service):
    """Test test_render with missing required variables"""
    variables = [
        TemplateVariable(name="required_field", type="string", required=True),
    ]

    result = template_service.create_template(
        template_type="test_render_missing",
        name="Test Missing",
        category="collections",
        template_content="<html>{{ required_field }}</html>",
        variables=variables,
    )

    template_id = result["id"]

    # Test render with missing data
    rendered, errors = template_service.test_render(
        template_id, {}  # Missing required_field
    )

    assert len(errors) > 0
    assert any("required_field" in err for err in errors)
