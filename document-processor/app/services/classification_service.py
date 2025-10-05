from __future__ import annotations

import re
from typing import Any, Dict

from ..models import DocumentClassification


class MockOpenAIService:
    """
    Mock OpenAI service for document classification.
    In production, this would use the actual OpenAI API.
    """
    
    def __init__(self):
        # In production, initialize with:
        # self.client = openai.AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        pass
    
    async def classify_document(self, text: str) -> DocumentClassification:
        """
        Classify document using rule-based logic (mock).
        
        In production, this would use GPT-4 to:
        1. Identify document type
        2. Extract relevant fields
        3. Return structured data with confidence scores
        
        Args:
            text: Document text content
        
        Returns:
            DocumentClassification with type, confidence, and extracted fields
        """
        # Simple rule-based classification for testing
        text_lower = text.lower()
        
        # Lease Agreement
        if any(keyword in text_lower for keyword in ['lease agreement', 'tenant', 'landlord', 'rent', 'premises']):
            return self._classify_lease_agreement(text)
        
        # Work Order
        elif any(keyword in text_lower for keyword in ['work order', 'repair', 'maintenance', 'service request']):
            return self._classify_work_order(text)
        
        # Payment Receipt
        elif any(keyword in text_lower for keyword in ['receipt', 'payment received', 'paid in full']):
            return self._classify_payment_receipt(text)
        
        # Maintenance Report
        elif any(keyword in text_lower for keyword in ['maintenance report', 'inspection', 'condition']):
            return self._classify_maintenance_report(text)
        
        # Court Notice
        elif any(keyword in text_lower for keyword in ['court', 'summons', 'eviction', 'notice to quit']):
            return self._classify_court_notice(text)
        
        # Tenant Application
        elif any(keyword in text_lower for keyword in ['application', 'applicant', 'rental application']):
            return self._classify_tenant_application(text)
        
        # Unknown
        else:
            return DocumentClassification(
                type="unknown",
                confidence=0.3,
                extracted_fields={}
            )
    
    def _classify_lease_agreement(self, text: str) -> DocumentClassification:
        """Extract fields from lease agreement"""
        fields = {}
        
        # Extract tenant name
        tenant_match = re.search(r'tenant[:\s]+([A-Za-z\s]+)', text, re.IGNORECASE)
        if tenant_match:
            fields['tenant_name'] = tenant_match.group(1).strip()
        
        # Extract landlord name
        landlord_match = re.search(r'landlord[:\s]+([A-Za-z\s]+)', text, re.IGNORECASE)
        if landlord_match:
            fields['landlord_name'] = landlord_match.group(1).strip()
        
        # Extract rent amount
        rent_match = re.search(r'rent[:\s]+\$?([0-9,]+\.?\d*)', text, re.IGNORECASE)
        if rent_match:
            fields['monthly_rent'] = rent_match.group(1).replace(',', '')
        
        # Extract lease term
        term_match = re.search(r'term[:\s]+(\d+)\s*(month|year)', text, re.IGNORECASE)
        if term_match:
            fields['lease_term'] = f"{term_match.group(1)} {term_match.group(2)}s"
        
        # Extract dates
        date_match = re.search(r'(\d{1,2}/\d{1,2}/\d{4})', text)
        if date_match:
            fields['start_date'] = date_match.group(1)
        
        confidence = 0.7 + (len(fields) * 0.05)
        
        return DocumentClassification(
            type="lease_agreement",
            confidence=min(confidence, 0.95),
            extracted_fields=fields
        )
    
    def _classify_work_order(self, text: str) -> DocumentClassification:
        """Extract fields from work order"""
        fields = {}
        
        # Extract work order number
        wo_match = re.search(r'(?:work order|wo)[#:\s]+([A-Z0-9-]+)', text, re.IGNORECASE)
        if wo_match:
            fields['work_order_number'] = wo_match.group(1)
        
        # Extract property/unit
        unit_match = re.search(r'unit[:\s]+([A-Z0-9-]+)', text, re.IGNORECASE)
        if unit_match:
            fields['unit'] = unit_match.group(1)
        
        # Extract issue description
        issue_match = re.search(r'(?:issue|problem|description)[:\s]+([^\n]{10,100})', text, re.IGNORECASE)
        if issue_match:
            fields['issue_description'] = issue_match.group(1).strip()
        
        # Extract priority
        if 'urgent' in text.lower() or 'emergency' in text.lower():
            fields['priority'] = 'high'
        elif 'routine' in text.lower():
            fields['priority'] = 'low'
        else:
            fields['priority'] = 'medium'
        
        confidence = 0.75 + (len(fields) * 0.05)
        
        return DocumentClassification(
            type="work_order",
            confidence=min(confidence, 0.95),
            extracted_fields=fields
        )
    
    def _classify_payment_receipt(self, text: str) -> DocumentClassification:
        """Extract fields from payment receipt"""
        fields = {}
        
        # Extract amount
        amount_match = re.search(r'(?:amount|total|paid)[:\s]+\$?([0-9,]+\.?\d*)', text, re.IGNORECASE)
        if amount_match:
            fields['amount'] = amount_match.group(1).replace(',', '')
        
        # Extract date
        date_match = re.search(r'(?:date|paid on)[:\s]+(\d{1,2}/\d{1,2}/\d{4})', text, re.IGNORECASE)
        if date_match:
            fields['payment_date'] = date_match.group(1)
        
        # Extract payment method
        if 'check' in text.lower():
            fields['payment_method'] = 'check'
        elif 'cash' in text.lower():
            fields['payment_method'] = 'cash'
        elif 'card' in text.lower() or 'credit' in text.lower():
            fields['payment_method'] = 'card'
        
        confidence = 0.8 + (len(fields) * 0.04)
        
        return DocumentClassification(
            type="payment_receipt",
            confidence=min(confidence, 0.95),
            extracted_fields=fields
        )
    
    def _classify_maintenance_report(self, text: str) -> DocumentClassification:
        """Extract fields from maintenance report"""
        fields = {}
        
        # Extract inspector name
        inspector_match = re.search(r'inspector[:\s]+([A-Za-z\s]+)', text, re.IGNORECASE)
        if inspector_match:
            fields['inspector'] = inspector_match.group(1).strip()
        
        # Extract inspection date
        date_match = re.search(r'(?:inspection date|inspected on)[:\s]+(\d{1,2}/\d{1,2}/\d{4})', text, re.IGNORECASE)
        if date_match:
            fields['inspection_date'] = date_match.group(1)
        
        # Extract condition
        if 'excellent' in text.lower():
            fields['condition'] = 'excellent'
        elif 'good' in text.lower():
            fields['condition'] = 'good'
        elif 'fair' in text.lower():
            fields['condition'] = 'fair'
        elif 'poor' in text.lower():
            fields['condition'] = 'poor'
        
        confidence = 0.75 + (len(fields) * 0.05)
        
        return DocumentClassification(
            type="maintenance_report",
            confidence=min(confidence, 0.95),
            extracted_fields=fields
        )
    
    def _classify_court_notice(self, text: str) -> DocumentClassification:
        """Extract fields from court notice"""
        fields = {}
        
        # Extract case number
        case_match = re.search(r'case[#:\s]+([A-Z0-9-]+)', text, re.IGNORECASE)
        if case_match:
            fields['case_number'] = case_match.group(1)
        
        # Extract court name
        court_match = re.search(r'([A-Za-z\s]+court)', text, re.IGNORECASE)
        if court_match:
            fields['court_name'] = court_match.group(1).strip()
        
        # Extract hearing date
        hearing_match = re.search(r'hearing[:\s]+(\d{1,2}/\d{1,2}/\d{4})', text, re.IGNORECASE)
        if hearing_match:
            fields['hearing_date'] = hearing_match.group(1)
        
        confidence = 0.8 + (len(fields) * 0.04)
        
        return DocumentClassification(
            type="court_notice",
            confidence=min(confidence, 0.95),
            extracted_fields=fields
        )
    
    def _classify_tenant_application(self, text: str) -> DocumentClassification:
        """Extract fields from tenant application"""
        fields = {}
        
        # Extract applicant name
        name_match = re.search(r'(?:applicant|name)[:\s]+([A-Za-z\s]+)', text, re.IGNORECASE)
        if name_match:
            fields['applicant_name'] = name_match.group(1).strip()
        
        # Extract phone
        phone_match = re.search(r'phone[:\s]+([0-9\-\(\)\s]+)', text, re.IGNORECASE)
        if phone_match:
            fields['phone'] = phone_match.group(1).strip()
        
        # Extract email
        email_match = re.search(r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})', text)
        if email_match:
            fields['email'] = email_match.group(1)
        
        # Extract income
        income_match = re.search(r'income[:\s]+\$?([0-9,]+)', text, re.IGNORECASE)
        if income_match:
            fields['annual_income'] = income_match.group(1).replace(',', '')
        
        confidence = 0.75 + (len(fields) * 0.04)
        
        return DocumentClassification(
            type="tenant_application",
            confidence=min(confidence, 0.95),
            extracted_fields=fields
        )


class ClassificationService:
    """
    Service for classifying and extracting data from documents.
    """
    
    def __init__(self, openai_service: MockOpenAIService | None = None):
        self.openai = openai_service or MockOpenAIService()
    
    async def classify_document(self, text: str) -> DocumentClassification:
        """
        Classify a document and extract relevant fields.
        
        Args:
            text: Document text content
        
        Returns:
            DocumentClassification with type, confidence, and extracted fields
        """
        return await self.openai.classify_document(text)

