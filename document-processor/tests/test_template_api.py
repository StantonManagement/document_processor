import pytest
from app.main import app, rl
from fastapi.testclient import TestClient

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    """Reset rate limiter before each test"""
    rl.bucket.clear()
    rl.max = 10000
    yield
    rl.max = 10


def test_create_template():
    """Test creating a template via API"""
    response = client.post(
        "/templates",
        json={
            "template_type": "test_api_template",
            "name": "Test API Template",
            "category": "collections",
            "state": "CA",
            "template_content": "<html><body>{{ tenant_name }}</body></html>",
            "variables": [
                {
                    "name": "tenant_name",
                    "type": "string",
                    "required": True,
                    "description": "Tenant name",
                }
            ],
            "requires_signature": False,
            "legal_compliance_notes": "Test compliance notes",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert "id" in data
    assert data["template_type"] == "test_api_template"
    assert data["version"] >= 1  # May be > 1 if run multiple times
    assert data["status"] == "active"

    return data["id"]


def test_create_template_invalid_syntax():
    """Test creating a template with invalid Jinja2 syntax"""
    response = client.post(
        "/templates",
        json={
            "template_type": "invalid_template",
            "name": "Invalid Template",
            "category": "collections",
            "template_content": "<html>{{ invalid syntax </html>",
            "variables": [],
        },
    )

    assert response.status_code == 400


def test_list_templates():
    """Test listing templates"""
    # First create a template
    test_create_template()

    # Now list templates
    response = client.get("/templates")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0


def test_list_templates_with_filters():
    """Test listing templates with filters"""
    # Create templates with different categories
    client.post(
        "/templates",
        json={
            "template_type": "filter_test_1",
            "name": "Filter Test 1",
            "category": "collections",
            "template_content": "<html>Test</html>",
            "variables": [],
        },
    )

    client.post(
        "/templates",
        json={
            "template_type": "filter_test_2",
            "name": "Filter Test 2",
            "category": "maintenance",
            "template_content": "<html>Test</html>",
            "variables": [],
        },
    )

    # Filter by category
    response = client.get("/templates?category=collections")
    assert response.status_code == 200
    data = response.json()
    assert all(t["category"] == "collections" for t in data)


def test_get_template():
    """Test getting a specific template"""
    # Create a template first
    template_id = test_create_template()

    # Get the template
    response = client.get(f"/templates/{template_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == template_id
    assert "template_content" in data
    assert "variables" in data


def test_get_template_not_found():
    """Test getting a non-existent template"""
    response = client.get("/templates/invalid-id")
    assert response.status_code == 404


def test_update_template():
    """Test updating a template"""
    # Create a template first
    template_id = test_create_template()

    # Update it
    response = client.patch(
        f"/templates/{template_id}",
        json={"name": "Updated Template Name", "status": "deprecated"},
    )

    assert response.status_code == 200

    # Verify the update
    response = client.get(f"/templates/{template_id}")
    data = response.json()
    assert data["name"] == "Updated Template Name"
    assert data["status"] == "deprecated"


def test_update_template_not_found():
    """Test updating a non-existent template"""
    response = client.patch("/templates/invalid-id", json={"name": "New Name"})
    assert response.status_code == 404


def test_test_render_template():
    """Test the test-render endpoint"""
    # Create a template first
    template_id = test_create_template()

    # Test render it
    response = client.post(
        f"/templates/{template_id}/test-render",
        json={"data": {"tenant_name": "John Smith"}},
    )

    assert response.status_code == 200
    data = response.json()
    assert "rendered_html" in data
    assert "John Smith" in data["rendered_html"]
    assert data["success"] is True


def test_test_render_template_missing_required():
    """Test test-render with missing required variables"""
    # Create a template with required variables
    response = client.post(
        "/templates",
        json={
            "template_type": "test_required",
            "name": "Test Required",
            "category": "collections",
            "template_content": "<html>{{ required_field }}</html>",
            "variables": [
                {"name": "required_field", "type": "string", "required": True}
            ],
        },
    )

    template_id = response.json()["id"]

    # Test render without required field
    response = client.post(f"/templates/{template_id}/test-render", json={"data": {}})

    assert response.status_code == 200
    data = response.json()
    assert len(data["validation_errors"]) > 0


def test_test_render_template_not_found():
    """Test test-render with non-existent template"""
    response = client.post("/templates/invalid-id/test-render", json={"data": {}})
    assert response.status_code == 404
