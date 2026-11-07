
"""
Evidence Management Service

Provides validated CRUD operations for evidence records.

Evidence associations with SWOT, PESTLE, Five Forces and Value Chain
are managed separately by app.strategic_analysis.evidence_service.

All write operations and their audit entries are committed atomically.
"""

import sqlite3

from app.database.connection import get_db
from app.services.audit_service import record_audit_log
from app.strategic_analysis.validation import (
    StrategicAnalysisValidationError,
    validate_positive_id,
    validate_required_text,
    validate_optional_text,
    validate_score,
    validate_choice,
)


class EvidenceError(Exception):
    """Base exception for evidence management errors."""


class EvidenceValidationError(EvidenceError):
    """Raised when evidence input is invalid."""


class EvidenceNotFoundError(EvidenceError):
    """Raised when an evidence record does not exist."""


class EvidencePermissionError(EvidenceError):
    """Raised when the acting user cannot perform an operation."""


# Must match the existing evidence.source_type CHECK constraint.
EVIDENCE_SOURCE_TYPES = (
    "Manual",
    "CSV Import",
    "External Source",
    "Internal Research",
    "Document",
)

EVIDENCE_FIELDS = {
    "title",
    "description",
    "source_type",
    "source_name",
    "source_url",
    "file_path",
    "entity_type",
    "entity_id",
    "reliability_score",
}


def _validate_input(callback, *args, **kwargs):
    try:
        return callback(*args, **kwargs)
    except StrategicAnalysisValidationError as exc:
        raise EvidenceValidationError(str(exc)) from exc


def _validate_actor(actor_id):
    actor_id = _validate_input(validate_positive_id, actor_id, "acting_user_id")

    row = get_db().execute(
        """
        SELECT id, role, is_active
        FROM users
        WHERE id = ?
        """,
        (actor_id,),
    ).fetchone()

    if row is None or not row["is_active"]:
        raise EvidencePermissionError("The acting user does not exist or is inactive.")

    return actor_id


def _validate_evidence_id(evidence_id):
    return _validate_input(
        validate_positive_id,
        evidence_id,
        "evidence_id",
    )


def _validate_title(title):
    return _validate_input(
        validate_required_text,
        title,
        "title",
    )


def _validate_optional(value, field_name):
    return _validate_input(
        validate_optional_text,
        value,
        field_name,
    )


def _validate_source_type(source_type):
    return _validate_input(
        validate_choice,
        source_type,
        EVIDENCE_SOURCE_TYPES,
        "source_type",
    )


def _validate_reliability_score(score):
    if score is None or score == "":
        return None

    return _validate_input(
        validate_score,
        score,
        "reliability_score",
    )


def _validate_entity_id(entity_id):
    if entity_id is None or entity_id == "":
        return None

    return _validate_input(
        validate_positive_id,
        entity_id,
        "entity_id",
    )


def _validate_entity_reference(entity_type, entity_id):
    """
    Validate the optional entity reference.

    The existing evidence table uses a polymorphic entity_type/entity_id
    association and does not define a foreign key for it. Therefore, this
    service validates the supported entity type and checks the referenced
    record where applicable.
    """

    entity_type = _validate_optional(entity_type, "entity_type")
    entity_id = _validate_entity_id(entity_id)

    if not entity_type and entity_id is not None:
        raise EvidenceValidationError(
            "entity_type is required when entity_id is supplied."
        )

    if entity_type and entity_id is None:
        raise EvidenceValidationError(
            "entity_id is required when entity_type is supplied."
        )

    if not entity_type:
        return None, None

    supported_entities = {
        "Company": "companies",
    }

    table_name = supported_entities.get(entity_type)

    if table_name is None:
        raise EvidenceValidationError(
            "Unsupported entity_type. Supported type: Company."
        )

    # Table name comes only from the fixed allowlist above.
    row = get_db().execute(
        f"SELECT id FROM {table_name} WHERE id = ?",
        (entity_id,),
    ).fetchone()

    if row is None:
        raise EvidenceValidationError(
            f"The referenced {entity_type.lower()} does not exist."
        )

    return entity_type, entity_id


def _row_to_dict(row):
    return dict(row) if row is not None else None


def _begin_transaction(database):
    if database.in_transaction:
        raise EvidenceError(
            "An existing database transaction is active. "
            "Evidence operations require their own transaction."
        )

    database.execute("BEGIN IMMEDIATE")


def _rollback(database):
    if database.in_transaction:
        database.rollback()


def _record_audit(
    actor_id,
    action,
    evidence_id,
    description,
):
    record_audit_log(
        user_id=actor_id,
        action=action,
        entity_type="Evidence",
        entity_id=evidence_id,
        description=description,
        commit=False,
    )


def create_evidence(
    title,
    acting_user_id,
    description=None,
    source_type="Manual",
    source_name=None,
    source_url=None,
    file_path=None,
    entity_type=None,
    entity_id=None,
    reliability_score=None,
):
    """Create an evidence record and its audit entry."""

    database = get_db()

    try:
        actor_id = _validate_actor(acting_user_id)
        title = _validate_title(title)
        description = _validate_optional(description, "description")
        source_type = _validate_source_type(source_type)
        source_name = _validate_optional(source_name, "source_name")
        source_url = _validate_optional(source_url, "source_url")
        file_path = _validate_optional(file_path, "file_path")

        entity_type, entity_id = _validate_entity_reference(
            entity_type,
            entity_id,
        )

        reliability_score = _validate_reliability_score(
            reliability_score
        )

        _begin_transaction(database)

        cursor = database.execute(
            """
            INSERT INTO evidence (
                title,
                description,
                source_type,
                source_name,
                source_url,
                file_path,
                entity_type,
                entity_id,
                reliability_score,
                uploaded_by
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                title,
                description,
                source_type,
                source_name,
                source_url,
                file_path,
                entity_type,
                entity_id,
                reliability_score,
                actor_id,
            ),
        )

        evidence_id = cursor.lastrowid

        _record_audit(
            actor_id,
            "CREATE_EVIDENCE",
            evidence_id,
            f"Created evidence record: {title}",
        )

        database.commit()

        return get_evidence_details(evidence_id)

    except EvidenceError:
        _rollback(database)
        raise
    except StrategicAnalysisValidationError as exc:
        _rollback(database)
        raise EvidenceValidationError(str(exc)) from exc
    except sqlite3.IntegrityError as exc:
        _rollback(database)
        raise EvidenceValidationError(
            "The evidence record could not be created because of a database constraint."
        ) from exc
    except Exception:
        _rollback(database)
        raise


def get_evidence_details(evidence_id):
    """Retrieve one evidence record by ID."""

    evidence_id = _validate_evidence_id(evidence_id)

    row = get_db().execute(
        """
        SELECT
            e.id,
            e.title,
            e.description,
            e.source_type,
            e.source_name,
            e.source_url,
            e.file_path,
            e.entity_type,
            e.entity_id,
            e.reliability_score,
            e.uploaded_by,
            e.created_at,
            u.full_name AS uploaded_by_name
        FROM evidence e
        LEFT JOIN users u ON u.id = e.uploaded_by
        WHERE e.id = ?
        """,
        (evidence_id,),
    ).fetchone()

    if row is None:
        raise EvidenceNotFoundError(
            f"Evidence record {evidence_id} was not found."
        )

    return _row_to_dict(row)


def get_evidence_records(
    limit=100,
    offset=0,
    source_type=None,
    entity_type=None,
    entity_id=None,
    search=None,
):
    """List evidence records with optional filters and pagination."""

    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 500:
        raise EvidenceValidationError("limit must be an integer between 1 and 500.")

    if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
        raise EvidenceValidationError("offset must be a non-negative integer.")

    conditions = []
    parameters = []

    if source_type is not None:
        source_type = _validate_source_type(source_type)
        conditions.append("e.source_type = ?")
        parameters.append(source_type)

    if entity_type is not None:
        entity_type = _validate_optional(entity_type, "entity_type")
        conditions.append("e.entity_type = ?")
        parameters.append(entity_type)

    if entity_id is not None:
        entity_id = _validate_entity_id(entity_id)
        conditions.append("e.entity_id = ?")
        parameters.append(entity_id)

    if search is not None:
        search = _validate_optional(search, "search")
        if search:
            conditions.append(
                """
                (
                    e.title LIKE ?
                    OR e.description LIKE ?
                    OR e.source_name LIKE ?
                )
                """
            )
            search_pattern = f"%{search}%"
            parameters.extend(
                [search_pattern, search_pattern, search_pattern]
            )

    where_clause = (
        "WHERE " + " AND ".join(conditions)
        if conditions
        else ""
    )

    query = f"""
        SELECT
            e.id,
            e.title,
            e.description,
            e.source_type,
            e.source_name,
            e.source_url,
            e.file_path,
            e.entity_type,
            e.entity_id,
            e.reliability_score,
            e.uploaded_by,
            e.created_at,
            u.full_name AS uploaded_by_name
        FROM evidence e
        LEFT JOIN users u ON u.id = e.uploaded_by
        {where_clause}
        ORDER BY e.created_at DESC, e.id DESC
        LIMIT ? OFFSET ?
    """

    parameters.extend([limit, offset])

    rows = get_db().execute(query, parameters).fetchall()

    return [_row_to_dict(row) for row in rows]


def update_evidence(evidence_id, acting_user_id, updates):
    """Update permitted evidence metadata and record the change."""

    database = get_db()

    if not isinstance(updates, dict) or not updates:
        raise EvidenceValidationError(
            "updates must be a non-empty dictionary."
        )

    unknown_fields = set(updates) - EVIDENCE_FIELDS

    if unknown_fields:
        raise EvidenceValidationError(
            "Unsupported evidence fields: "
            + ", ".join(sorted(unknown_fields))
        )

    try:
        actor_id = _validate_actor(acting_user_id)
        evidence_id = _validate_evidence_id(evidence_id)

        current = get_evidence_details(evidence_id)

        values = {
            "title": current["title"],
            "description": current["description"],
            "source_type": current["source_type"],
            "source_name": current["source_name"],
            "source_url": current["source_url"],
            "file_path": current["file_path"],
            "entity_type": current["entity_type"],
            "entity_id": current["entity_id"],
            "reliability_score": current["reliability_score"],
        }

        values.update(updates)

        values["title"] = _validate_title(values["title"])
        values["description"] = _validate_optional(
            values["description"], "description"
        )
        values["source_type"] = _validate_source_type(
            values["source_type"]
        )
        values["source_name"] = _validate_optional(
            values["source_name"], "source_name"
        )
        values["source_url"] = _validate_optional(
            values["source_url"], "source_url"
        )
        values["file_path"] = _validate_optional(
            values["file_path"], "file_path"
        )
        values["entity_type"], values["entity_id"] = (
            _validate_entity_reference(
                values["entity_type"],
                values["entity_id"],
            )
        )
        values["reliability_score"] = _validate_reliability_score(
            values["reliability_score"]
        )

        _begin_transaction(database)

        database.execute(
            """
            UPDATE evidence
            SET
                title = ?,
                description = ?,
                source_type = ?,
                source_name = ?,
                source_url = ?,
                file_path = ?,
                entity_type = ?,
                entity_id = ?,
                reliability_score = ?
            WHERE id = ?
            """,
            (
                values["title"],
                values["description"],
                values["source_type"],
                values["source_name"],
                values["source_url"],
                values["file_path"],
                values["entity_type"],
                values["entity_id"],
                values["reliability_score"],
                evidence_id,
            ),
        )

        _record_audit(
            actor_id,
            "UPDATE_EVIDENCE",
            evidence_id,
            f"Updated evidence record: {values['title']}",
        )

        database.commit()

        return get_evidence_details(evidence_id)

    except EvidenceError:
        _rollback(database)
        raise
    except StrategicAnalysisValidationError as exc:
        _rollback(database)
        raise EvidenceValidationError(str(exc)) from exc
    except sqlite3.IntegrityError as exc:
        _rollback(database)
        raise EvidenceValidationError(
            "The evidence record could not be updated because of a database constraint."
        ) from exc
    except Exception:
        _rollback(database)
        raise


def delete_evidence(evidence_id, acting_user_id):
    """
    Delete an evidence record.

    The existing database foreign key cascades deletion to its
    strategic_analysis_evidence associations. The evidence record
    and its audit entry are handled in one transaction.
    """

    database = get_db()

    try:
        actor_id = _validate_actor(acting_user_id)
        evidence_id = _validate_evidence_id(evidence_id)

        evidence = get_evidence_details(evidence_id)

        _begin_transaction(database)

        linked_count = database.execute(
            """
            SELECT COUNT(*) AS total
            FROM strategic_analysis_evidence
            WHERE evidence_id = ?
            """,
            (evidence_id,),
        ).fetchone()["total"]

        database.execute(
            "DELETE FROM evidence WHERE id = ?",
            (evidence_id,),
        )

        _record_audit(
            actor_id,
            "DELETE_EVIDENCE",
            evidence_id,
            (
                f"Deleted evidence record: {evidence['title']}. "
                f"Associated strategic-analysis links removed: {linked_count}."
            ),
        )

        database.commit()

        return {
            "id": evidence_id,
            "deleted": True,
            "removed_associations": linked_count,
        }

    except EvidenceError:
        _rollback(database)
        raise
    except sqlite3.IntegrityError as exc:
        _rollback(database)
        raise EvidenceError(
            "The evidence record could not be deleted because of a database constraint."
        ) from exc
    except Exception:
        _rollback(database)
        raise
