import json
import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Dict, Optional

DB_PATH = os.getenv("DATABASE_PATH", os.path.join(os.path.dirname(__file__), "app.db"))


def _dict_factory(cursor, row):
    return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}


def init_db() -> None:
    # Initialize database with sane defaults for concurrency under tests
    with sqlite3.connect(DB_PATH, timeout=5.0) as conn:
        # Improve concurrency: WAL allows readers and writers to operate concurrently
        try:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            conn.execute("PRAGMA busy_timeout=3000;")
        except Exception:
            # Pragmas are best-effort; continue if not supported
            pass
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS documents (
                id TEXT PRIMARY KEY,
                file_name TEXT NOT NULL,
                file_type TEXT NOT NULL,
                file_size INTEGER NOT NULL,
                status TEXT NOT NULL,
                raw_text TEXT,
                parsed_data TEXT,
                error_message TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS processing_logs (
                id TEXT PRIMARY KEY,
                document_id TEXT NOT NULL,
                action TEXT NOT NULL,
                status TEXT NOT NULL,
                details TEXT,
                created_at TEXT NOT NULL
            );
            """
        )

        # New tables for document generation
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS document_templates (
                id TEXT PRIMARY KEY,
                template_type TEXT NOT NULL,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                state TEXT,
                version INTEGER DEFAULT 1,
                template_content TEXT NOT NULL,
                variables TEXT NOT NULL,
                requires_signature INTEGER DEFAULT 0,
                legal_compliance_notes TEXT,
                status TEXT DEFAULT 'active',
                created_by TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(template_type, state, version)
            );
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS generated_documents (
                id TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                storage_key TEXT NOT NULL,
                template_id TEXT,
                template_type TEXT,
                category TEXT NOT NULL,
                tenant_id INTEGER,
                property_id INTEGER,
                unit_id INTEGER,
                created_by TEXT NOT NULL,
                workflow_id TEXT,
                requires_signature INTEGER DEFAULT 0,
                signature_status TEXT,
                signature_request_id TEXT,
                signed_at TEXT,
                signed_document_key TEXT,
                file_size INTEGER,
                metadata TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (template_id) REFERENCES document_templates(id)
            );
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS document_access_log (
                id TEXT PRIMARY KEY,
                document_id TEXT NOT NULL,
                accessed_by TEXT NOT NULL,
                access_type TEXT NOT NULL,
                ip_address TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (document_id) REFERENCES generated_documents(id)
            );
            """
        )

        # Create indexes for better query performance
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_generated_docs_tenant ON generated_documents(tenant_id);"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_generated_docs_template_type ON generated_documents(template_type);"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_generated_docs_signature_status ON generated_documents(signature_status);"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_templates_type_state ON document_templates(template_type, state);"
        )

        conn.commit()


@contextmanager
def get_conn(dict_mode: bool = False):
    # Use a connection timeout to reduce 'database is locked' errors under concurrency
    conn = sqlite3.connect(DB_PATH, timeout=5.0)
    if dict_mode:
        conn.row_factory = _dict_factory
    try:
        # Ensure a reasonable busy timeout at the connection level
        try:
            conn.execute("PRAGMA busy_timeout=3000;")
        except Exception:
            pass
        yield conn
    finally:
        conn.close()


class DocumentRepository:
    def create_document(
        self,
        file_name: str,
        file_type: str,
        file_size: int,
        uploaded_by: str = "system",
    ) -> Dict[str, Any]:
        now = datetime.utcnow().isoformat()
        doc_id = str(uuid.uuid4())
        with get_conn() as conn:
            conn.execute(
                """
                INSERT INTO documents (id, file_name, file_type, file_size, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, 'pending', ?, ?)
                """,
                (doc_id, file_name, file_type, file_size, now, now),
            )
            conn.commit()
        self.log_action(
            doc_id, "create_document", "pending", {"uploaded_by": uploaded_by}
        )
        return {"id": doc_id, "status": "pending", "created_at": now, "updated_at": now}

    def update_status(
        self,
        document_id: str,
        status: str,
        *,
        error_message: Optional[str] = None,
        raw_text: Optional[str] = None,
        parsed_data: Optional[Dict[str, Any]] = None,
    ) -> None:
        now = datetime.utcnow().isoformat()
        with get_conn() as conn:
            conn.execute(
                """
                UPDATE documents
                SET status = ?, error_message = ?, raw_text = COALESCE(?, raw_text), parsed_data = COALESCE(?, parsed_data), updated_at = ?
                WHERE id = ?
                """,
                (
                    status,
                    error_message,
                    raw_text,
                    json.dumps(parsed_data) if parsed_data is not None else None,
                    now,
                    document_id,
                ),
            )
            conn.commit()
        self.log_action(document_id, "update_status", status, {"error": error_message})

    def get_document(self, document_id: str) -> Optional[Dict[str, Any]]:
        with get_conn(dict_mode=True) as conn:
            cur = conn.execute("SELECT * FROM documents WHERE id = ?", (document_id,))
            row = cur.fetchone()
            if row and row.get("parsed_data"):
                try:
                    row["parsed_data"] = (
                        json.loads(row["parsed_data"]) if row["parsed_data"] else None
                    )
                except Exception:
                    row["parsed_data"] = None
            return row

    def log_action(
        self,
        document_id: str,
        action: str,
        status: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        with get_conn() as conn:
            conn.execute(
                """
                INSERT INTO processing_logs (id, document_id, action, status, details, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    document_id,
                    action,
                    status,
                    json.dumps(details or {}),
                    datetime.utcnow().isoformat(),
                ),
            )
            conn.commit()


class TemplateRepository:
    def create_template(
        self,
        template_type: str,
        name: str,
        category: str,
        template_content: str,
        variables: str,
        state: Optional[str] = None,
        requires_signature: bool = False,
        legal_compliance_notes: Optional[str] = None,
        created_by: str = "system",
    ) -> Dict[str, Any]:
        now = datetime.utcnow().isoformat()
        template_id = str(uuid.uuid4())

        # Get next version number for this template_type and state
        with get_conn() as conn:
            cur = conn.execute(
                """
                SELECT COALESCE(MAX(version), 0) + 1 as next_version
                FROM document_templates
                WHERE template_type = ? AND (state = ? OR (state IS NULL AND ? IS NULL))
                """,
                (template_type, state, state),
            )
            version = cur.fetchone()[0]

            conn.execute(
                """
                INSERT INTO document_templates (
                    id, template_type, name, category, state, version,
                    template_content, variables, requires_signature,
                    legal_compliance_notes, status, created_by, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?, ?)
                """,
                (
                    template_id,
                    template_type,
                    name,
                    category,
                    state,
                    version,
                    template_content,
                    variables,
                    1 if requires_signature else 0,
                    legal_compliance_notes,
                    created_by,
                    now,
                    now,
                ),
            )
            conn.commit()

        return {
            "id": template_id,
            "template_type": template_type,
            "version": version,
            "status": "active",
            "created_at": now,
        }

    def get_template(self, template_id: str) -> Optional[Dict[str, Any]]:
        with get_conn(dict_mode=True) as conn:
            cur = conn.execute(
                "SELECT * FROM document_templates WHERE id = ?", (template_id,)
            )
            row = cur.fetchone()
            if row:
                # Convert integer to boolean for requires_signature
                row["requires_signature"] = bool(row.get("requires_signature", 0))
            return row

    def list_templates(
        self,
        category: Optional[str] = None,
        state: Optional[str] = None,
        template_type: Optional[str] = None,
        active_only: bool = True,
    ) -> list[Dict[str, Any]]:
        with get_conn(dict_mode=True) as conn:
            query = "SELECT * FROM document_templates WHERE 1=1"
            params = []

            if category:
                query += " AND category = ?"
                params.append(category)
            if state:
                query += " AND state = ?"
                params.append(state)
            if template_type:
                query += " AND template_type = ?"
                params.append(template_type)
            if active_only:
                query += " AND status = 'active'"

            query += " ORDER BY created_at DESC"

            cur = conn.execute(query, params)
            rows = cur.fetchall()
            for row in rows:
                row["requires_signature"] = bool(row.get("requires_signature", 0))
            return rows

    def update_template(self, template_id: str, **kwargs) -> None:
        now = datetime.utcnow().isoformat()
        with get_conn() as conn:
            # Build dynamic update query
            fields = []
            values = []
            for key, value in kwargs.items():
                if key in [
                    "name",
                    "template_content",
                    "variables",
                    "legal_compliance_notes",
                    "status",
                ]:
                    fields.append(f"{key} = ?")
                    values.append(value)
                elif key == "requires_signature":
                    fields.append("requires_signature = ?")
                    values.append(1 if value else 0)

            if fields:
                fields.append("updated_at = ?")
                values.append(now)
                values.append(template_id)

                query = (
                    f"UPDATE document_templates SET {', '.join(fields)} WHERE id = ?"
                )
                conn.execute(query, values)
                conn.commit()


class GeneratedDocumentRepository:
    def create_document(
        self,
        filename: str,
        storage_key: str,
        category: str,
        created_by: str,
        template_id: Optional[str] = None,
        template_type: Optional[str] = None,
        tenant_id: Optional[int] = None,
        property_id: Optional[int] = None,
        unit_id: Optional[int] = None,
        workflow_id: Optional[str] = None,
        requires_signature: bool = False,
        file_size: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        now = datetime.utcnow().isoformat()
        doc_id = str(uuid.uuid4())

        signature_status = "not_required" if not requires_signature else "pending"

        with get_conn() as conn:
            conn.execute(
                """
                INSERT INTO generated_documents (
                    id, filename, storage_key, template_id, template_type, category,
                    tenant_id, property_id, unit_id, created_by, workflow_id,
                    requires_signature, signature_status, file_size, metadata,
                    created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    doc_id,
                    filename,
                    storage_key,
                    template_id,
                    template_type,
                    category,
                    tenant_id,
                    property_id,
                    unit_id,
                    created_by,
                    workflow_id,
                    1 if requires_signature else 0,
                    signature_status,
                    file_size,
                    json.dumps(metadata or {}),
                    now,
                    now,
                ),
            )
            conn.commit()

        return {
            "id": doc_id,
            "status": "generated",
            "signature_status": signature_status,
            "created_at": now,
        }

    def get_document(self, document_id: str) -> Optional[Dict[str, Any]]:
        with get_conn(dict_mode=True) as conn:
            cur = conn.execute(
                "SELECT * FROM generated_documents WHERE id = ?", (document_id,)
            )
            row = cur.fetchone()
            if row:
                row["requires_signature"] = bool(row.get("requires_signature", 0))
                if row.get("metadata"):
                    try:
                        row["metadata"] = json.loads(row["metadata"])
                    except Exception:
                        row["metadata"] = {}
            return row

    def update_storage_key(self, document_id: str, storage_key: str) -> None:
        """Update the storage key for a document"""
        now = datetime.utcnow().isoformat()
        with get_conn() as conn:
            conn.execute(
                """
                UPDATE generated_documents
                SET storage_key = ?, updated_at = ?
                WHERE id = ?
                """,
                (storage_key, now, document_id),
            )
            conn.commit()

    def update_signature_status(
        self,
        document_id: str,
        signature_status: str,
        signature_request_id: Optional[str] = None,
        signed_at: Optional[str] = None,
        signed_document_key: Optional[str] = None,
    ) -> None:
        now = datetime.utcnow().isoformat()
        with get_conn() as conn:
            conn.execute(
                """
                UPDATE generated_documents
                SET signature_status = ?,
                    signature_request_id = COALESCE(?, signature_request_id),
                    signed_at = COALESCE(?, signed_at),
                    signed_document_key = COALESCE(?, signed_document_key),
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    signature_status,
                    signature_request_id,
                    signed_at,
                    signed_document_key,
                    now,
                    document_id,
                ),
            )
            conn.commit()

    def log_access(
        self,
        document_id: str,
        accessed_by: str,
        access_type: str,
        ip_address: Optional[str] = None,
    ) -> None:
        with get_conn() as conn:
            conn.execute(
                """
                INSERT INTO document_access_log (id, document_id, accessed_by, access_type, ip_address, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    document_id,
                    accessed_by,
                    access_type,
                    ip_address,
                    datetime.utcnow().isoformat(),
                ),
            )
            conn.commit()


repo = DocumentRepository()
template_repo = TemplateRepository()
generated_doc_repo = GeneratedDocumentRepository()
init_db()
