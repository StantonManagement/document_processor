from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Optional
from datetime import datetime, timedelta


class LocalStorageService:
    """
    Local file storage service (mock implementation for testing).
    In production, this would be replaced with S3/R2 integration.
    """
    
    def __init__(self, base_path: Optional[str] = None):
        self.base_path = Path(base_path or os.getenv(
            "STORAGE_PATH", 
            os.path.join(os.path.dirname(__file__), "..", "storage")
        ))
        self.base_path.mkdir(parents=True, exist_ok=True)
    
    def store_file(
        self,
        file_bytes: bytes,
        storage_key: str,
    ) -> str:
        """
        Store file locally and return the storage key.
        
        Args:
            file_bytes: File content as bytes
            storage_key: Path-like key for the file (e.g., "documents/collections/uuid/file.pdf")
        
        Returns:
            Storage key of the stored file
        """
        file_path = self.base_path / storage_key
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(file_path, 'wb') as f:
            f.write(file_bytes)
        
        return storage_key
    
    def get_file(self, storage_key: str) -> Optional[bytes]:
        """
        Retrieve file content by storage key.
        
        Args:
            storage_key: Path-like key for the file
        
        Returns:
            File content as bytes, or None if not found
        """
        file_path = self.base_path / storage_key
        
        if not file_path.exists():
            return None
        
        with open(file_path, 'rb') as f:
            return f.read()
    
    def delete_file(self, storage_key: str) -> bool:
        """
        Delete file by storage key.
        
        Args:
            storage_key: Path-like key for the file
        
        Returns:
            True if deleted, False if not found
        """
        file_path = self.base_path / storage_key
        
        if not file_path.exists():
            return False
        
        file_path.unlink()
        return True
    
    def generate_presigned_url(
        self,
        storage_key: str,
        expires_in: int = 3600,
    ) -> str:
        """
        Generate a presigned URL for file access.
        
        In local mock mode, this returns a simple path-based URL.
        In production with S3/R2, this would generate a real presigned URL.
        
        Args:
            storage_key: Path-like key for the file
            expires_in: URL expiration time in seconds (not enforced in mock)
        
        Returns:
            URL string for accessing the file
        """
        # In mock mode, return a simple URL pattern
        # In production, this would use boto3's generate_presigned_url
        base_url = os.getenv("APP_URL", "http://localhost:8000")
        return f"{base_url}/storage/{storage_key}"
    
    def file_exists(self, storage_key: str) -> bool:
        """Check if file exists"""
        file_path = self.base_path / storage_key
        return file_path.exists()
    
    def get_file_size(self, storage_key: str) -> Optional[int]:
        """Get file size in bytes"""
        file_path = self.base_path / storage_key
        
        if not file_path.exists():
            return None
        
        return file_path.stat().st_size


class MockSupabaseService:
    """
    Mock Supabase service for testing.
    In production, this would use the actual Supabase client.
    """
    
    def __init__(self):
        # In production, initialize with:
        # self.client = create_client(
        #     os.getenv("SUPABASE_URL"),
        #     os.getenv("SUPABASE_KEY")
        # )
        pass
    
    def table(self, table_name: str):
        """Mock table method - returns self for chaining"""
        return self
    
    def insert(self, data: dict):
        """Mock insert - in production would insert to Supabase"""
        return self
    
    def select(self, *args):
        """Mock select - in production would query Supabase"""
        return self
    
    def eq(self, column: str, value):
        """Mock equality filter"""
        return self
    
    def execute(self):
        """Mock execute - returns empty result"""
        class MockResult:
            data = []
        return MockResult()


class DocumentStorageService:
    """
    High-level document storage service that combines local storage
    and metadata management.
    """
    
    def __init__(
        self,
        storage: Optional[LocalStorageService] = None,
        supabase: Optional[MockSupabaseService] = None,
    ):
        self.storage = storage or LocalStorageService()
        self.supabase = supabase or MockSupabaseService()
    
    def store_document(
        self,
        document_id: str,
        document_bytes: bytes,
        filename: str,
        category: str,
        metadata: dict,
    ) -> str:
        """
        Store document and return presigned URL.
        
        Args:
            document_id: Unique document identifier
            document_bytes: Document content
            filename: Original filename
            category: Document category (collections, maintenance, leasing)
            metadata: Additional metadata
        
        Returns:
            Presigned URL for document access
        """
        # Generate storage key
        storage_key = f"documents/{category}/{document_id}/{filename}"
        
        # Store file
        self.storage.store_file(document_bytes, storage_key)
        
        # Generate presigned URL
        url = self.storage.generate_presigned_url(storage_key)
        
        return url
    
    def get_document_url(
        self,
        storage_key: str,
        expires_in: int = 3600,
    ) -> str:
        """
        Get presigned URL for document access.
        
        Args:
            storage_key: Storage key of the document
            expires_in: URL expiration time in seconds
        
        Returns:
            Presigned URL
        """
        return self.storage.generate_presigned_url(storage_key, expires_in)
    
    def get_document_bytes(self, storage_key: str) -> Optional[bytes]:
        """Get document content as bytes"""
        return self.storage.get_file(storage_key)

