
"""
StrategySim - Strategic Analysis Evidence Service.

Manages evidence associations for:
    - SWOT factors
    - PESTLE factors
    - Five Forces indicators
    - Value Chain activities

Design:
    - One analytical record can have multiple evidence records.
    - One evidence record can support multiple analytical records.
    - Duplicate associations are rejected.
    - Analytical record existence is validated by analysis type.
    - Existing evidence records are never modified or deleted.
    - Audit logging is performed within the same transaction.
"""

import sqlite3

from app.database.connection import get_db
from app.services.audit_service import record_audit_log

from app.strategic_analysis.validation import (
    StrategicAnalysisValidationError,
    validate_positive_id,
    validate_choice,
)


# =========================================================
# EXCEPTIONS
# =========================================================

class EvidenceLinkError(Exception):
    """Base exception for evidence-link operations."""


class EvidenceLinkNotFoundError(EvidenceLinkError):
    """Raised when an evidence link or referenced record is missing."""


class EvidenceLinkDuplicateError(EvidenceLinkError):
    """Raised when the requested evidence link already exists."""


# =========================================================
# CONFIGURATION
# =========================================================

ANALYSIS_RECORD_TABLES = {
    "SWOT": "swot_factors",
    "PESTLE": "pestle_factors",
    "FIVE_FORCES": "five_forces_indicators",
    "VALUE_CHAIN": "value_chain_activities",
}

EVIDENCE_COLUMNS = """
    e.id AS evidence_id,
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
    e.created_at AS evidence_created_at
"""


# =========================================================
# INTERNAL HELPERS
# =========================================================

def _get_analysis_type(analysis_type):
    """Validate and normalize the analytical module type."""

    try:
        return validate_choice(
            analysis_type,
            set(ANALYSIS_RECORD_TABLES.keys()),
            field="Analysis type",
        )
    except StrategicAnalysisValidationError as error:
        raise EvidenceLinkError(str(error)) from error


def _get_actor_id(acting_user_id):
    """Validate the ID of the user performing the operation."""

    try:
        return validate_positive_id(
            acting_user_id,
            field="Acting user ID",
        )
    except StrategicAnalysisValidationError as error:
        raise EvidenceLinkError(str(error)) from error


def _get_record_id(record_id):
    """Validate an analytical record ID."""

    try:
        return validate_positive_id(
            record_id,
            field="Analysis record ID",
        )
    except StrategicAnalysisValidationError as error:
        raise EvidenceLinkError(str(error)) from error


def _get_evidence_id(evidence_id):
    """Validate an evidence record ID."""

    try:
        return validate_positive_id(
            evidence_id,
            field="Evidence ID",
        )
    except StrategicAnalysisValidationError as error:
        raise EvidenceLinkError(str(error)) from error


def _get_db_connection():
    """Return the existing Flask database connection."""

    return get_db()


def _begin_transaction(connection):
    """Start an immediate SQLite transaction."""

    if connection.in_transaction:
        raise EvidenceLinkError(
            "Cannot start evidence operation inside an existing transaction."
        )

    connection.execute("BEGIN IMMEDIATE")


def _validate_actor(connection, acting_user_id):
    """
    Confirm that the acting user exists.

    Role authorization is enforced by the existing RBAC decorators
    in the route layer. This check additionally protects the audit
    foreign-key relationship.
    """

    user = connection.execute(
        """
        SELECT id
        FROM users
        WHERE id = ?
        """,
        (acting_user_id,),
    ).fetchone()

    if user is None:
        raise EvidenceLinkError(
            "The acting user does not exist."
        )


def _validate_evidence(connection, evidence_id):
    """Confirm that the evidence record exists."""

    evidence = connection.execute(
        """
        SELECT id
        FROM evidence
        WHERE id = ?
        """,
        (evidence_id,),
    ).fetchone()

    if evidence is None:
        raise EvidenceLinkNotFoundError(
            f"Evidence record {evidence_id} does not exist."
        )


def _validate_analysis_record(
    connection,
    analysis_type,
    analysis_record_id,
):
    """Confirm that the analytical record exists."""

    table_name = ANALYSIS_RECORD_TABLES[analysis_type]

    record = connection.execute(
        f"""
        SELECT id
        FROM {table_name}
        WHERE id = ?
        """,
        (analysis_record_id,),
    ).fetchone()

    if record is None:
        raise EvidenceLinkNotFoundError(
            f"{analysis_type} analytical record "
            f"{analysis_record_id} does not exist."
        )


def _row_to_dict(row):
    """Convert a SQLite row into a regular dictionary."""

    if row is None:
        return None

    return dict(row)


def _rollback(connection):
    """Roll back an active transaction safely."""

    if connection.in_transaction:
        connection.rollback()


# =========================================================
# CREATE EVIDENCE LINK
# =========================================================

def create_evidence_link(
    evidence_id,
    analysis_type,
    analysis_record_id,
    acting_user_id,
):
    """
    Link an existing evidence record to an analytical record.

    Parameters:
        evidence_id:
            Existing ID from the evidence table.

        analysis_type:
            SWOT, PESTLE, FIVE_FORCES or VALUE_CHAIN.

        analysis_record_id:
            ID of the factor, indicator or activity.

        acting_user_id:
            ID of the authenticated Administrator or Analyst.

    Returns:
        Dictionary containing the newly created association.

    Raises:
        EvidenceLinkError:
            For invalid inputs or database failures.

        EvidenceLinkNotFoundError:
            If the evidence or analytical record does not exist.

        EvidenceLinkDuplicateError:
            If the association already exists.
    """

    evidence_id = _get_evidence_id(evidence_id)
    analysis_type = _get_analysis_type(analysis_type)
    analysis_record_id = _get_record_id(analysis_record_id)
    acting_user_id = _get_actor_id(acting_user_id)

    connection = _get_db_connection()

    try:
        _begin_transaction(connection)

        _validate_actor(connection, acting_user_id)

        _validate_evidence(connection, evidence_id)

        _validate_analysis_record(
            connection,
            analysis_type,
            analysis_record_id,
        )

        cursor = connection.execute(
            """
            INSERT INTO strategic_analysis_evidence (
                evidence_id,
                analysis_type,
                analysis_record_id
            )
            VALUES (?, ?, ?)
            """,
            (
                evidence_id,
                analysis_type,
                analysis_record_id,
            ),
        )

        link_id = cursor.lastrowid

        record_audit_log(
            user_id=acting_user_id,
            action="CREATE",
            entity_type="strategic_analysis_evidence",
            entity_id=link_id,
            description=(
                f"Linked evidence record {evidence_id} "
                f"to {analysis_type} record {analysis_record_id}."
            ),
            commit=False,
        )

        connection.commit()

        return {
            "id": link_id,
            "evidence_id": evidence_id,
            "analysis_type": analysis_type,
            "analysis_record_id": analysis_record_id,
        }

    except sqlite3.IntegrityError as error:
        _rollback(connection)

        error_message = str(error).lower()

        if (
            "unique constraint failed" in error_message
            or "unique constraint" in error_message
        ):
            raise EvidenceLinkDuplicateError(
                "This evidence record is already linked "
                "to the selected analytical record."
            ) from error

        raise EvidenceLinkError(
            f"Database constraint prevented evidence linking: {error}"
        ) from error

    except EvidenceLinkError:
        _rollback(connection)
        raise

    except Exception as error:
        _rollback(connection)

        raise EvidenceLinkError(
            f"Unable to create evidence link: {error}"
        ) from error


# =========================================================
# GET EVIDENCE LINKS FOR AN ANALYTICAL RECORD
# =========================================================

def get_evidence_links(
    analysis_type,
    analysis_record_id,
):
    """
    Retrieve all evidence records linked to an analytical record.

    Returns:
        List of dictionaries containing association and evidence data.
    """

    analysis_type = _get_analysis_type(analysis_type)
    analysis_record_id = _get_record_id(analysis_record_id)

    table_name = ANALYSIS_RECORD_TABLES[analysis_type]
    connection = _get_db_connection()

    _validate_analysis_record(
        connection,
        analysis_type,
        analysis_record_id,
    )

    rows = connection.execute(
        f"""
        SELECT
            sa.id AS link_id,
            sa.analysis_type,
            sa.analysis_record_id,
            sa.created_at AS linked_at,
            {EVIDENCE_COLUMNS}
        FROM strategic_analysis_evidence sa
        INNER JOIN evidence e
            ON e.id = sa.evidence_id
        WHERE sa.analysis_type = ?
          AND sa.analysis_record_id = ?
        ORDER BY sa.created_at DESC, sa.id DESC
        """,
        (
            analysis_type,
            analysis_record_id,
        ),
    ).fetchall()

    return [_row_to_dict(row) for row in rows]


# =========================================================
# GET ALL ANALYTICAL LINKS FOR AN EVIDENCE RECORD
# =========================================================

def get_evidence_analysis_links(evidence_id):
    """
    Retrieve every analytical record supported by an evidence record.

    This provides the reverse lookup:
        Evidence -> SWOT / PESTLE / Five Forces / Value Chain.

    Returns:
        List of dictionaries containing link details.
    """

    evidence_id = _get_evidence_id(evidence_id)

    connection = _get_db_connection()

    _validate_evidence(connection, evidence_id)

    rows = connection.execute(
        """
        SELECT
            id AS link_id,
            evidence_id,
            analysis_type,
            analysis_record_id,
            created_at AS linked_at
        FROM strategic_analysis_evidence
        WHERE evidence_id = ?
        ORDER BY created_at DESC, id DESC
        """,
        (evidence_id,),
    ).fetchall()

    return [_row_to_dict(row) for row in rows]


# =========================================================
# GET A SINGLE EVIDENCE LINK
# =========================================================

def get_evidence_link_details(link_id):
    """
    Retrieve one evidence association with its evidence metadata.

    Returns:
        Dictionary or None.
    """

    link_id = _get_record_id(link_id)

    connection = _get_db_connection()

    row = connection.execute(
        f"""
        SELECT
            sa.id AS link_id,
            sa.analysis_type,
            sa.analysis_record_id,
            sa.created_at AS linked_at,
            {EVIDENCE_COLUMNS}
        FROM strategic_analysis_evidence sa
        INNER JOIN evidence e
            ON e.id = sa.evidence_id
        WHERE sa.id = ?
        """,
        (link_id,),
    ).fetchone()

    return _row_to_dict(row)


# =========================================================
# DELETE EVIDENCE LINK
# =========================================================

def delete_evidence_link(
    link_id,
    acting_user_id,
):
    """
    Remove an evidence association without deleting the evidence.

    The evidence record itself remains unchanged.

    Returns:
        True when the association is removed.
    """

    link_id = _get_record_id(link_id)
    acting_user_id = _get_actor_id(acting_user_id)

    connection = _get_db_connection()

    try:
        _begin_transaction(connection)

        _validate_actor(connection, acting_user_id)

        link = connection.execute(
            """
            SELECT
                id,
                evidence_id,
                analysis_type,
                analysis_record_id
            FROM strategic_analysis_evidence
            WHERE id = ?
            """,
            (link_id,),
        ).fetchone()

        if link is None:
            raise EvidenceLinkNotFoundError(
                f"Evidence link {link_id} does not exist."
            )

        connection.execute(
            """
            DELETE FROM strategic_analysis_evidence
            WHERE id = ?
            """,
            (link_id,),
        )

        record_audit_log(
            user_id=acting_user_id,
            action="DELETE",
            entity_type="strategic_analysis_evidence",
            entity_id=link_id,
            description=(
                f"Removed evidence link {link_id}: "
                f"evidence {link['evidence_id']} from "
                f"{link['analysis_type']} record "
                f"{link['analysis_record_id']}."
            ),
            commit=False,
        )

        connection.commit()

        return True

    except EvidenceLinkNotFoundError:
        _rollback(connection)
        raise

    except EvidenceLinkError:
        _rollback(connection)
        raise

    except Exception as error:
        _rollback(connection)

        raise EvidenceLinkError(
            f"Unable to delete evidence link: {error}"
        ) from error
