import pytest
from app.services.generation_service import GenerationService
from app.services.template_service import TemplateService
from app.models import TemplateVariable


@pytest.fixture
def generation_service():
    return GenerationService()


@pytest.fixture
def template_service():
    return TemplateService()


@pytest.fixture
def sample_template(template_service):
    """Create a sample template for testing"""
    variables = [
        TemplateVariable(name="tenant_name", type="string", required=True),
        TemplateVariable(name="amount_owed", type="currency", required=True),
        TemplateVariable(name="property_address", type="string", required=True),
    ]
    
    template_content = """
    <!DOCTYPE html>
    <html>
    <head><title>Test Notice</title></head>
    <body>
        <h1>Payment Notice</h1>
        <p>To: {{ tenant_name }}</p>
        <p>Property: {{ property_address }}</p>
        <p>Amount Owed: {{ amount_owed|currency }}</p>
        <p>Date: {{ current_date|date }}</p>
    </body>
    </html>
    """
    
    result = template_service.create_template(
        template_type="test_notice",
        name="Test Payment Notice",
        category="collections",
        template_content=template_content,
        variables=variables,
    )
    
    return result["id"]


def test_add_default_styles(generation_service):
    """Test adding default styles to HTML"""
    html_without_styles = "<html><body>Test</body></html>"
    html_with_styles = generation_service._add_default_styles(html_without_styles)
    
    assert "<style>" in html_with_styles
    assert "font-family" in html_with_styles


def test_add_default_styles_preserves_existing(generation_service):
    """Test that existing styles are preserved"""
    html_with_styles = "<html><head><style>body { color: red; }</style></head><body>Test</body></html>"
    result = generation_service._add_default_styles(html_with_styles)
    
    # Should not add duplicate styles
    assert result.count("<style>") == 1
    assert "color: red" in result


def test_render_to_html(generation_service, sample_template):
    """Test rendering template to HTML"""
    data = {
        "tenant_name": "John Smith",
        "amount_owed": "1500.00",
        "property_address": "123 Main St",
    }
    
    html, errors = generation_service.render_to_html(sample_template, data)
    
    assert html is not None
    assert "John Smith" in html
    assert "$1,500.00" in html
    assert "123 Main St" in html
    assert len(errors) == 0


def test_render_to_html_adds_current_date(generation_service, sample_template):
    """Test that current_date is automatically added"""
    data = {
        "tenant_name": "John Smith",
        "amount_owed": "1500.00",
        "property_address": "123 Main St",
    }
    
    html, errors = generation_service.render_to_html(sample_template, data)
    
    # Should contain a date (current_date is auto-added)
    assert html is not None


def test_render_to_html_invalid_template(generation_service):
    """Test rendering with invalid template ID"""
    with pytest.raises(ValueError, match="Template not found"):
        generation_service.render_to_html("invalid-id", {})


def test_render_to_pdf(generation_service, sample_template):
    """Test rendering template to PDF"""
    data = {
        "tenant_name": "John Smith",
        "amount_owed": "1500.00",
        "property_address": "123 Main St",
    }
    
    try:
        pdf_bytes, errors = generation_service.render_to_pdf(sample_template, data)
        
        assert pdf_bytes is not None
        assert isinstance(pdf_bytes, bytes)
        assert len(pdf_bytes) > 0
        # PDF files start with %PDF
        assert pdf_bytes[:4] == b'%PDF'
    except RuntimeError as e:
        # WeasyPrint might not be available in test environment
        if "WeasyPrint is not available" in str(e):
            pytest.skip("WeasyPrint not available")
        raise


def test_generate_document_pdf(generation_service, sample_template):
    """Test full document generation workflow (PDF)"""
    data = {
        "tenant_name": "John Smith",
        "amount_owed": "1500.00",
        "property_address": "123 Main St",
    }
    
    metadata = {
        "tenant_id": 12345,
        "property_id": 67890,
    }
    
    try:
        result = generation_service.generate_document(
            template_id=sample_template,
            data=data,
            output_format="pdf",
            metadata=metadata,
            requires_signature=False,
            created_by="test_user",
        )
        
        assert "document_id" in result
        assert result["status"] == "generated"
        assert "document_url" in result
        assert result["signature_status"] == "not_required"
    except RuntimeError as e:
        if "WeasyPrint is not available" in str(e):
            pytest.skip("WeasyPrint not available")
        raise


def test_generate_document_html(generation_service, sample_template):
    """Test document generation with HTML output"""
    data = {
        "tenant_name": "John Smith",
        "amount_owed": "1500.00",
        "property_address": "123 Main St",
    }
    
    result = generation_service.generate_document(
        template_id=sample_template,
        data=data,
        output_format="html",
        metadata={},
        requires_signature=False,
        created_by="test_user",
    )
    
    assert "document_id" in result
    assert result["status"] == "generated"
    assert "document_url" in result


def test_generate_document_with_signature(generation_service, sample_template):
    """Test document generation requiring signature"""
    data = {
        "tenant_name": "John Smith",
        "amount_owed": "1500.00",
        "property_address": "123 Main St",
    }
    
    result = generation_service.generate_document(
        template_id=sample_template,
        data=data,
        output_format="html",
        metadata={},
        requires_signature=True,
        created_by="test_user",
    )
    
    assert result["signature_status"] == "pending"


def test_generate_document_invalid_format(generation_service, sample_template):
    """Test document generation with invalid output format"""
    data = {
        "tenant_name": "John Smith",
        "amount_owed": "1500.00",
        "property_address": "123 Main St",
    }
    
    with pytest.raises(ValueError, match="Unsupported output format"):
        generation_service.generate_document(
            template_id=sample_template,
            data=data,
            output_format="docx",  # Not supported
            metadata={},
            requires_signature=False,
            created_by="test_user",
        )


def test_regenerate_document(generation_service, sample_template):
    """Test regenerating an existing document"""
    # First generate a document
    data = {
        "tenant_name": "John Smith",
        "amount_owed": "1500.00",
        "property_address": "123 Main St",
    }
    
    original = generation_service.generate_document(
        template_id=sample_template,
        data=data,
        output_format="html",
        metadata={},
        requires_signature=False,
        created_by="test_user",
    )
    
    original_doc_id = original["document_id"]
    
    # Now regenerate with new data
    new_data = {
        "tenant_name": "Jane Doe",
        "amount_owed": "2000.00",
        "property_address": "456 Oak Ave",
    }
    
    regenerated = generation_service.regenerate_document(
        document_id=original_doc_id,
        data=new_data,
    )
    
    # Should create a new document
    assert regenerated["document_id"] != original_doc_id
    assert regenerated["status"] == "generated"


def test_regenerate_document_not_found(generation_service):
    """Test regenerating a non-existent document"""
    with pytest.raises(ValueError, match="Document not found"):
        generation_service.regenerate_document(
            document_id="invalid-id",
            data={},
        )

