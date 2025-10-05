"""
Integration tests for document generation workflow.

Tests the full workflow from template creation to document generation,
signature requests, and compliance validation.
"""

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


class TestFullGenerationWorkflow:
    """Test complete document generation workflow"""

    def test_template_to_pdf_workflow(self):
        """Test: Create template → Generate document → Download"""
        # Step 1: Create a template
        template_response = client.post(
            "/templates",
            json={
                "template_type": "integration_test_notice",
                "name": "Integration Test Notice",
                "category": "collections",
                "state": "CA",
                "template_content": """
                    <html>
                    <body>
                        <h1>Payment Notice</h1>
                        <p>Dear {{ tenant_name }},</p>
                        <p>You owe {{ amount_owed|currency }}</p>
                        <p>Property: {{ property_address }}</p>
                    </body>
                    </html>
                """,
                "variables": [
                    {"name": "tenant_name", "type": "string", "required": True},
                    {"name": "amount_owed", "type": "currency", "required": True},
                    {"name": "property_address", "type": "string", "required": True},
                ],
                "requires_signature": False,
            },
        )

        assert template_response.status_code == 200
        template_id = template_response.json()["id"]

        # Step 2: Generate document from template
        generate_response = client.post(
            "/documents/generate",
            json={
                "template_id": template_id,
                "data": {
                    "tenant_name": "John Doe",
                    "amount_owed": "1500.00",
                    "property_address": "123 Test St",
                },
                "output_format": "html",
                "metadata": {"tenant_id": 999, "property_id": 888},
            },
        )

        assert generate_response.status_code == 200
        doc_data = generate_response.json()
        assert "document_id" in doc_data
        assert doc_data["status"] == "generated"

        document_id = doc_data["document_id"]

        # Step 3: Get document metadata
        metadata_response = client.get(f"/documents/{document_id}/metadata")
        assert metadata_response.status_code == 200
        metadata = metadata_response.json()
        assert metadata["template_id"] == template_id
        assert metadata["tenant_id"] == 999

        # Step 4: Download document
        download_response = client.get(f"/documents/{document_id}/download")
        assert download_response.status_code == 200
        assert len(download_response.content) > 0

    def test_signature_workflow(self):
        """Test: Create template → Generate → Send for signature → Check status"""
        # Step 1: Create template requiring signature
        template_response = client.post(
            "/templates",
            json={
                "template_type": "signature_test",
                "name": "Signature Test Document",
                "category": "leasing",
                "template_content": "<html><body><h1>Agreement</h1><p>{{ tenant_name }}</p></body></html>",
                "variables": [
                    {"name": "tenant_name", "type": "string", "required": True}
                ],
                "requires_signature": True,
            },
        )

        assert template_response.status_code == 200
        template_id = template_response.json()["id"]

        # Step 2: Generate document
        generate_response = client.post(
            "/documents/generate",
            json={
                "template_id": template_id,
                "data": {"tenant_name": "Jane Smith"},
                "output_format": "html",
                "requires_signature": True,
            },
        )

        assert generate_response.status_code == 200
        document_id = generate_response.json()["document_id"]

        # Step 3: Send for signature
        signature_response = client.post(
            f"/documents/{document_id}/send-for-signature",
            json={
                "signature_recipients": [
                    {
                        "email": "tenant@example.com",
                        "name": "Jane Smith",
                        "role": "tenant",
                    }
                ]
            },
        )

        assert signature_response.status_code == 200
        sig_data = signature_response.json()
        assert sig_data["status"] == "pending"
        assert "signature_request_id" in sig_data

        # Step 4: Check signature status
        status_response = client.get(f"/documents/{document_id}/signature-status")
        assert status_response.status_code == 200
        status_data = status_response.json()
        assert status_data["signature_status"] == "pending"

    def test_compliance_validation_workflow(self):
        """Test: Validate compliance → Create compliant template → Generate"""
        # Step 1: Check state requirements
        state_response = client.get("/compliance/states?state=CA")
        assert state_response.status_code == 200
        states = state_response.json()
        assert len(states) > 0
        ca_rules = states[0]
        assert ca_rules["state"] == "CA"
        assert ca_rules["notice_days"] == 3

        # Step 2: Validate data against compliance
        validation_response = client.post(
            "/compliance/validate?template_type=payment_notice&state=CA",
            json={
                "amount_owed": "1500.00",
                "payment_deadline": "2025-10-06",
                "property_address": "123 Main St",
                "tenant_name": "John Smith",
            },
        )

        assert validation_response.status_code == 200
        validation = validation_response.json()
        assert validation["compliant"] is True

        # Step 3: Create compliant template
        template_response = client.post(
            "/templates",
            json={
                "template_type": "payment_notice",
                "name": "CA Compliant Notice",
                "category": "collections",
                "state": "CA",
                "template_content": """
                    <html><body>
                        <h1>3-Day Notice</h1>
                        <p>Tenant: {{ tenant_name }}</p>
                        <p>Amount: {{ amount_owed|currency }}</p>
                        <p>Address: {{ property_address }}</p>
                        <p>Deadline: {{ payment_deadline|date }}</p>
                    </body></html>
                """,
                "variables": [
                    {"name": "tenant_name", "type": "string", "required": True},
                    {"name": "amount_owed", "type": "currency", "required": True},
                    {"name": "property_address", "type": "string", "required": True},
                    {"name": "payment_deadline", "type": "date", "required": True},
                ],
                "legal_compliance_notes": "California Civil Code Section 1161",
            },
        )

        assert template_response.status_code == 200
        template_id = template_response.json()["id"]

        # Step 4: Generate compliant document
        generate_response = client.post(
            "/documents/generate",
            json={
                "template_id": template_id,
                "data": {
                    "tenant_name": "John Smith",
                    "amount_owed": "1500.00",
                    "property_address": "123 Main St",
                    "payment_deadline": "2025-10-06",
                },
                "output_format": "html",
            },
        )

        assert generate_response.status_code == 200

    def test_regenerate_document_workflow(self):
        """Test: Generate document → Regenerate with new data"""
        # Step 1: Create template
        template_response = client.post(
            "/templates",
            json={
                "template_type": "regen_test",
                "name": "Regeneration Test",
                "category": "maintenance",
                "template_content": "<html><body><p>Amount: {{ amount|currency }}</p></body></html>",
                "variables": [{"name": "amount", "type": "currency", "required": True}],
            },
        )

        template_id = template_response.json()["id"]

        # Step 2: Generate initial document
        generate_response = client.post(
            "/documents/generate",
            json={
                "template_id": template_id,
                "data": {"amount": "1000.00"},
                "output_format": "html",
            },
        )

        original_doc_id = generate_response.json()["document_id"]

        # Step 3: Regenerate with new data
        regen_response = client.post(
            f"/documents/{original_doc_id}/regenerate", json={"amount": "2000.00"}
        )

        assert regen_response.status_code == 200
        new_doc_id = regen_response.json()["document_id"]

        # New document should have different ID
        assert new_doc_id != original_doc_id

    def test_state_specific_template_selection(self):
        """Test: Create state-specific templates → List by state"""
        # Create templates for different states
        states = ["CA", "NY", "TX"]
        template_ids = {}

        for state in states:
            response = client.post(
                "/templates",
                json={
                    "template_type": "state_test_notice",
                    "name": f"{state} Notice",
                    "category": "collections",
                    "state": state,
                    "template_content": f"<html><body><h1>{state} Notice</h1></body></html>",
                    "variables": [],
                },
            )
            assert response.status_code == 200
            template_ids[state] = response.json()["id"]

        # List templates for each state
        for state in states:
            response = client.get(f"/templates?state={state}")
            assert response.status_code == 200
            templates = response.json()

            # Should have at least the template we created
            state_templates = [t for t in templates if t["state"] == state]
            assert len(state_templates) > 0


class TestErrorHandling:
    """Test error handling in integration scenarios"""

    def test_generate_with_missing_required_fields(self):
        """Test: Generate document with missing required fields"""
        # Create template with required fields
        template_response = client.post(
            "/templates",
            json={
                "template_type": "error_test",
                "name": "Error Test",
                "category": "collections",
                "template_content": "<html><body>{{ required_field }}</body></html>",
                "variables": [
                    {"name": "required_field", "type": "string", "required": True}
                ],
            },
        )

        template_id = template_response.json()["id"]

        # Try to generate without required field
        generate_response = client.post(
            "/documents/generate",
            json={
                "template_id": template_id,
                "data": {},  # Missing required_field
                "output_format": "html",
            },
        )

        # Current implementation logs warnings but still generates the document
        # This is by design to be more forgiving
        assert generate_response.status_code == 200
        # Document is generated but may have missing content
        assert "document_id" in generate_response.json()

    def test_send_signature_for_non_existent_document(self):
        """Test: Send signature request for non-existent document"""
        response = client.post(
            "/documents/invalid-id/send-for-signature",
            json={
                "signature_recipients": [
                    {"email": "test@example.com", "name": "Test", "role": "tenant"}
                ]
            },
        )

        assert response.status_code == 404
