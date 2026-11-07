
"""
StrategySim - SWOT Analysis Services

Transactional CRUD operations for SWOT assessments and factors.

Permission policy is enforced by the route layer:
- Administrator: full access
- Analyst: full access
- Viewer: read-only

Evidence associations are managed through the shared
strategic_analysis.evidence_service module.
"""

import sqlite3

from app.database.connection import get_db
from app.services.audit_service import record_audit_log


# =========================================================
# CONSTANTS
# =========================================================

SWOT_FACTOR_TYPES = (
    "Strength",
    "Weakness",
    "Opportunity",
    "Threat",
)

MAX_ASSESSMENT_NAME_LENGTH = 150
MAX_FACTOR_NAME_LENGTH = 200
MAX_DESCRIPTION_LENGTH = 5000
MAX_SUMMARY_LENGTH = 10000


# =========================================================
# EXCEPTIONS
# =========================================================

class SWOTError(Exception):
    """Base exception for SWOT operations."""


class SWOTValidationError(SWOTError):
    """Raised when supplied SWOT data is invalid."""


class SWOTNotFoundError(SWOTError):
    """Raised when an assessment or factor does not exist."""


class SWOTPermissionError(SWOTError):
    """Raised when the acting user is invalid or inactive."""


class SWOTDuplicateError(SWOTError):
    """Raised when a duplicate SWOT record is detected."""


# =========================================================
# VALIDATION HELPERS
# =========================================================

def _validate_id(value, field_name):
    if isinstance(value, bool):
        raise SWOTValidationError(
            f"{field_name} must be a positive integer."
        )

    try:
        value = int(value)
    except (TypeError, ValueError):
        raise SWOTValidationError(
            f"{field_name} must be a positive integer."
        )

    if value <= 0:
        raise SWOTValidationError(
            f"{field_name} must be a positive integer."
        )

    return value


def _validate_required_text(value, field_name, max_length):
    if not isinstance(value, str):
        raise SWOTValidationError(
            f"{field_name} must be text."
        )

    value = value.strip()

    if not value:
        raise SWOTValidationError(
            f"{field_name} is required."
        )

    if len(value) > max_length:
        raise SWOTValidationError(
            f"{field_name} cannot exceed "
            f"{max_length} characters."
        )

    return value


def _validate_optional_text(value, field_name, max_length):
    if value is None:
        return None

    if not isinstance(value, str):
        raise SWOTValidationError(
            f"{field_name} must be text."
        )

    value = value.strip()

    if not value:
        return None

    if len(value) > max_length:
        raise SWOTValidationError(
            f"{field_name} cannot exceed "
            f"{max_length} characters."
        )

    return value


def _validate_importance(value):
    if value is None or value == "":
        return None

    if isinstance(value, bool):
        raise SWOTValidationError(
            "Strategic importance must be an integer "
            "between 1 and 5."
        )

    try:
        numeric_value = int(value)
    except (TypeError, ValueError):
        raise SWOTValidationError(
            "Strategic importance must be an integer "
            "between 1 and 5."
        )

    if numeric_value < 1 or numeric_value > 5:
        raise SWOTValidationError(
            "Strategic importance must be between 1 and 5."
        )

    return numeric_value


def _validate_factor_type(value):
    if not isinstance(value, str):
        raise SWOTValidationError(
            "Factor type must be text."
        )

    value = value.strip()

    if value not in SWOT_FACTOR_TYPES:
        raise SWOTValidationError(
            "Factor type must be one of: "
            + ", ".join(SWOT_FACTOR_TYPES)
        )

    return value


def _validate_assessment_date(value):
    if value is None or value == "":
        return None

    value = _validate_required_text(
        value,
        "Assessment date",
        30,
    )

    from datetime import date

    try:
        date.fromisoformat(value)
    except ValueError as error:
        raise SWOTValidationError(
            "Assessment date must use YYYY-MM-DD format."
        ) from error

    return value


# =========================================================
# DATABASE AND TRANSACTION HELPERS
# =========================================================

def _database():
    return get_db()


def _begin_transaction(database):
    if database.in_transaction:
        raise SWOTError(
            "A database transaction is already active."
        )

    database.execute("BEGIN IMMEDIATE")


def _rollback(database):
    if database.in_transaction:
        database.rollback()


def _validate_actor(database, acting_user_id):
    acting_user_id = _validate_id(
        acting_user_id,
        "Acting user ID",
    )

    user = database.execute(
        """
        SELECT id, role, is_active
        FROM users
        WHERE id = ?
        """,
        (acting_user_id,),
    ).fetchone()

    if user is None or not user["is_active"]:
        raise SWOTPermissionError(
            "The acting user does not exist or is inactive."
        )

    return acting_user_id


def _validate_company(database, company_id):
    company_id = _validate_id(
        company_id,
        "Company ID",
    )

    company = database.execute(
        """
        SELECT id
        FROM companies
        WHERE id = ?
        """,
        (company_id,),
    ).fetchone()

    if company is None:
        raise SWOTValidationError(
            "The selected company does not exist."
        )

    return company_id


def _get_assessment(database, assessment_id):
    assessment_id = _validate_id(
        assessment_id,
        "Assessment ID",
    )

    assessment = database.execute(
        """
        SELECT *
        FROM swot_assessments
        WHERE id = ?
        """,
        (assessment_id,),
    ).fetchone()

    if assessment is None:
        raise SWOTNotFoundError(
            "SWOT assessment was not found."
        )

    return assessment


def _get_factor(database, factor_id):
    factor_id = _validate_id(
        factor_id,
        "Factor ID",
    )

    factor = database.execute(
        """
        SELECT *
        FROM swot_factors
        WHERE id = ?
        """,
        (factor_id,),
    ).fetchone()

    if factor is None:
        raise SWOTNotFoundError(
            "SWOT factor was not found."
        )

    return factor


def _audit(
    acting_user_id,
    action,
    entity_type,
    entity_id,
    description,
):
    result = record_audit_log(
        user_id=acting_user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        description=description,
        commit=False,
    )

    if result is not True:
        raise SWOTError(
            "Audit log operation failed."
        )


def _row_to_dict(row):
    if row is None:
        return None

    return dict(row)


# =========================================================
# ASSESSMENT OPERATIONS
# =========================================================

def create_swot_assessment(
    company_id,
    assessment_name,
    acting_user_id,
    assessment_date=None,
    summary=None,
):
    """Create a SWOT assessment for an existing company."""

    database = _database()

    company_id = _validate_company(
        database,
        company_id,
    )

    assessment_name = _validate_required_text(
        assessment_name,
        "Assessment name",
        MAX_ASSESSMENT_NAME_LENGTH,
    )

    assessment_date = _validate_assessment_date(
        assessment_date
    )

    summary = _validate_optional_text(
        summary,
        "Summary",
        MAX_SUMMARY_LENGTH,
    )

    try:
        _begin_transaction(database)

        acting_user_id = _validate_actor(
            database,
            acting_user_id,
        )

        cursor = database.execute(
            """
            INSERT INTO swot_assessments (
                company_id,
                assessment_name,
                assessment_date,
                summary,
                created_by
            )
            VALUES (
                ?,
                ?,
                COALESCE(?, CURRENT_TIMESTAMP),
                ?,
                ?
            )
            """,
            (
                company_id,
                assessment_name,
                assessment_date,
                summary,
                acting_user_id,
            ),
        )

        assessment_id = cursor.lastrowid

        _audit(
            acting_user_id,
            "CREATE",
            "SWOT Assessment",
            assessment_id,
            f"Created SWOT assessment: {assessment_name}",
        )

        database.commit()

        return get_swot_assessment(assessment_id)

    except sqlite3.IntegrityError as error:
        _rollback(database)

        raise SWOTValidationError(
            f"Unable to create SWOT assessment: {error}"
        ) from error

    except Exception:
        _rollback(database)
        raise


def get_swot_assessment(assessment_id):
    """Get one assessment with company and factor details."""

    database = _database()

    assessment_id = _validate_id(
        assessment_id,
        "Assessment ID",
    )

    row = database.execute(
        """
        SELECT
            a.*,
            c.name AS company_name,
            u.full_name AS created_by_name
        FROM swot_assessments AS a
        JOIN companies AS c
            ON c.id = a.company_id
        LEFT JOIN users AS u
            ON u.id = a.created_by
        WHERE a.id = ?
        """,
        (assessment_id,),
    ).fetchone()

    if row is None:
        raise SWOTNotFoundError(
            "SWOT assessment was not found."
        )

    result = _row_to_dict(row)

    result["factors"] = get_swot_factors(
        assessment_id
    )

    return result


def get_swot_assessments(
    company_id=None,
    limit=100,
    offset=0,
    search=None,
):
    """List SWOT assessments with optional filters."""

    database = _database()

    if isinstance(limit, bool) or isinstance(offset, bool):
        raise SWOTValidationError(
            "Limit and offset must be valid integers."
        )

    try:
        limit = int(limit)
        offset = int(offset)
    except (TypeError, ValueError):
        raise SWOTValidationError(
            "Limit and offset must be integers."
        )

    if limit < 1 or limit > 500:
        raise SWOTValidationError(
            "Limit must be between 1 and 500."
        )

    if offset < 0:
        raise SWOTValidationError(
            "Offset cannot be negative."
        )

    conditions = []
    parameters = []

    if company_id is not None:
        company_id = _validate_id(
            company_id,
            "Company ID",
        )

        conditions.append("a.company_id = ?")
        parameters.append(company_id)

    if search:
        search = _validate_optional_text(
            search,
            "Search",
            150,
        )

        if search:
            conditions.append(
                """
                (
                    a.assessment_name LIKE ?
                    OR c.name LIKE ?
                )
                """
            )

            search_value = f"%{search}%"

            parameters.extend([
                search_value,
                search_value,
            ])

    where_clause = ""

    if conditions:
        where_clause = (
            "WHERE " + " AND ".join(conditions)
        )

    parameters.extend([limit, offset])

    rows = database.execute(
        f"""
        SELECT
            a.*,
            c.name AS company_name,
            u.full_name AS created_by_name,
            (
                SELECT COUNT(*)
                FROM swot_factors AS f
                WHERE f.assessment_id = a.id
            ) AS factor_count
        FROM swot_assessments AS a
        JOIN companies AS c
            ON c.id = a.company_id
        LEFT JOIN users AS u
            ON u.id = a.created_by
        {where_clause}
        ORDER BY a.created_at DESC, a.id DESC
        LIMIT ? OFFSET ?
        """,
        parameters,
    ).fetchall()

    return [
        _row_to_dict(row)
        for row in rows
    ]


def update_swot_assessment(
    assessment_id,
    acting_user_id,
    updates,
):
    """Update an existing SWOT assessment."""

    if not isinstance(updates, dict) or not updates:
        raise SWOTValidationError(
            "Updates must be a non-empty dictionary."
        )

    allowed_fields = {
        "assessment_name",
        "assessment_date",
        "summary",
    }

    unknown_fields = set(updates) - allowed_fields

    if unknown_fields:
        raise SWOTValidationError(
            "Unsupported assessment fields: "
            + ", ".join(sorted(unknown_fields))
        )

    validated = {}

    if "assessment_name" in updates:
        validated["assessment_name"] = (
            _validate_required_text(
                updates["assessment_name"],
                "Assessment name",
                MAX_ASSESSMENT_NAME_LENGTH,
            )
        )

    if "assessment_date" in updates:
        validated["assessment_date"] = (
            _validate_assessment_date(
                updates["assessment_date"]
            )
        )

    if "summary" in updates:
        validated["summary"] = (
            _validate_optional_text(
                updates["summary"],
                "Summary",
                MAX_SUMMARY_LENGTH,
            )
        )

    database = _database()

    assessment_id = _validate_id(
        assessment_id,
        "Assessment ID",
    )

    try:
        _begin_transaction(database)

        acting_user_id = _validate_actor(
            database,
            acting_user_id,
        )

        _get_assessment(
            database,
            assessment_id,
        )

        assignments = [
            f"{field} = ?"
            for field in validated
        ]

        assignments.append(
            "updated_at = CURRENT_TIMESTAMP"
        )

        values = list(validated.values())
        values.append(assessment_id)

        database.execute(
            f"""
            UPDATE swot_assessments
            SET {", ".join(assignments)}
            WHERE id = ?
            """,
            values,
        )

        _audit(
            acting_user_id,
            "UPDATE",
            "SWOT Assessment",
            assessment_id,
            "Updated SWOT assessment.",
        )

        database.commit()

        return get_swot_assessment(assessment_id)

    except Exception:
        _rollback(database)
        raise


def delete_swot_assessment(
    assessment_id,
    acting_user_id,
):
    """Delete an assessment, its factors and their evidence links."""

    database = _database()

    assessment_id = _validate_id(
        assessment_id,
        "Assessment ID",
    )

    try:
        _begin_transaction(database)

        acting_user_id = _validate_actor(
            database,
            acting_user_id,
        )

        assessment = _get_assessment(
            database,
            assessment_id,
        )

        factor_ids = database.execute(
            """
            SELECT id
            FROM swot_factors
            WHERE assessment_id = ?
            """,
            (assessment_id,),
        ).fetchall()

        for factor in factor_ids:
            database.execute(
                """
                DELETE FROM strategic_analysis_evidence
                WHERE analysis_type = 'SWOT'
                  AND analysis_record_id = ?
                """,
                (factor["id"],),
            )

        database.execute(
            """
            DELETE FROM swot_assessments
            WHERE id = ?
            """,
            (assessment_id,),
        )

        _audit(
            acting_user_id,
            "DELETE",
            "SWOT Assessment",
            assessment_id,
            (
                "Deleted SWOT assessment: "
                f"{assessment['assessment_name']}"
            ),
        )

        database.commit()

        return {
            "id": assessment_id,
            "deleted": True,
        }

    except Exception:
        _rollback(database)
        raise


# =========================================================
# FACTOR OPERATIONS
# =========================================================

def create_swot_factor(
    assessment_id,
    factor_type,
    factor_name,
    acting_user_id,
    description=None,
    importance=None,
):
    """Create a SWOT factor."""

    database = _database()

    assessment_id = _validate_id(
        assessment_id,
        "Assessment ID",
    )

    factor_type = _validate_factor_type(
        factor_type
    )

    factor_name = _validate_required_text(
        factor_name,
        "Factor name",
        MAX_FACTOR_NAME_LENGTH,
    )

    description = _validate_optional_text(
        description,
        "Description",
        MAX_DESCRIPTION_LENGTH,
    )

    strategic_importance = _validate_importance(
        importance
    )

    try:
        _begin_transaction(database)

        acting_user_id = _validate_actor(
            database,
            acting_user_id,
        )

        _get_assessment(
            database,
            assessment_id,
        )

        cursor = database.execute(
            """
            INSERT INTO swot_factors (
                assessment_id,
                factor_type,
                factor_name,
                description,
                strategic_importance
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                assessment_id,
                factor_type,
                factor_name,
                description,
                strategic_importance,
            ),
        )

        factor_id = cursor.lastrowid

        _audit(
            acting_user_id,
            "CREATE",
            "SWOT Factor",
            factor_id,
            (
                f"Created {factor_type} factor: "
                f"{factor_name}"
            ),
        )

        database.commit()

        return get_swot_factor(factor_id)

    except sqlite3.IntegrityError as error:
        _rollback(database)

        raise SWOTValidationError(
            f"Unable to create SWOT factor: {error}"
        ) from error

    except Exception:
        _rollback(database)
        raise


def get_swot_factor(factor_id):
    """Get a single SWOT factor with its assessment details."""

    database = _database()

    factor_id = _validate_id(
        factor_id,
        "Factor ID",
    )

    row = database.execute(
        """
        SELECT
            f.*,
            a.company_id,
            a.assessment_name,
            c.name AS company_name
        FROM swot_factors AS f
        JOIN swot_assessments AS a
            ON a.id = f.assessment_id
        JOIN companies AS c
            ON c.id = a.company_id
        WHERE f.id = ?
        """,
        (factor_id,),
    ).fetchone()

    if row is None:
        raise SWOTNotFoundError(
            "SWOT factor was not found."
        )

    return _row_to_dict(row)


def get_swot_factors(
    assessment_id,
    factor_type=None,
):
    """List factors belonging to an assessment."""

    database = _database()

    assessment_id = _validate_id(
        assessment_id,
        "Assessment ID",
    )

    _get_assessment(
        database,
        assessment_id,
    )

    parameters = [assessment_id]

    sql = """
        SELECT *
        FROM swot_factors
        WHERE assessment_id = ?
    """

    if factor_type is not None:
        factor_type = _validate_factor_type(
            factor_type
        )

        sql += " AND factor_type = ?"
        parameters.append(factor_type)

    sql += """
        ORDER BY
            CASE factor_type
                WHEN 'Strength' THEN 1
                WHEN 'Weakness' THEN 2
                WHEN 'Opportunity' THEN 3
                WHEN 'Threat' THEN 4
            END,
            strategic_importance DESC,
            id ASC
    """

    rows = database.execute(
        sql,
        parameters,
    ).fetchall()

    return [
        _row_to_dict(row)
        for row in rows
    ]


def update_swot_factor(
    factor_id,
    acting_user_id,
    updates,
):
    """Update an existing SWOT factor."""

    if not isinstance(updates, dict) or not updates:
        raise SWOTValidationError(
            "Updates must be a non-empty dictionary."
        )

    allowed_fields = {
        "factor_type",
        "factor_name",
        "description",
        "importance",
    }

    unknown_fields = set(updates) - allowed_fields

    if unknown_fields:
        raise SWOTValidationError(
            "Unsupported factor fields: "
            + ", ".join(sorted(unknown_fields))
        )

    validated = {}

    if "factor_type" in updates:
        validated["factor_type"] = (
            _validate_factor_type(
                updates["factor_type"]
            )
        )

    if "factor_name" in updates:
        validated["factor_name"] = (
            _validate_required_text(
                updates["factor_name"],
                "Factor name",
                MAX_FACTOR_NAME_LENGTH,
            )
        )

    if "description" in updates:
        validated["description"] = (
            _validate_optional_text(
                updates["description"],
                "Description",
                MAX_DESCRIPTION_LENGTH,
            )
        )

    if "importance" in updates:
        validated["strategic_importance"] = (
            _validate_importance(
                updates["importance"]
            )
        )

    database = _database()

    factor_id = _validate_id(
        factor_id,
        "Factor ID",
    )

    try:
        _begin_transaction(database)

        acting_user_id = _validate_actor(
            database,
            acting_user_id,
        )

        _get_factor(
            database,
            factor_id,
        )

        assignments = [
            f"{field} = ?"
            for field in validated
        ]

        assignments.append(
            "updated_at = CURRENT_TIMESTAMP"
        )

        values = list(validated.values())
        values.append(factor_id)

        database.execute(
            f"""
            UPDATE swot_factors
            SET {", ".join(assignments)}
            WHERE id = ?
            """,
            values,
        )

        _audit(
            acting_user_id,
            "UPDATE",
            "SWOT Factor",
            factor_id,
            "Updated SWOT factor.",
        )

        database.commit()

        return get_swot_factor(factor_id)

    except Exception:
        _rollback(database)
        raise


def delete_swot_factor(
    factor_id,
    acting_user_id,
):
    """Delete a factor and its evidence associations."""

    database = _database()

    factor_id = _validate_id(
        factor_id,
        "Factor ID",
    )

    try:
        _begin_transaction(database)

        acting_user_id = _validate_actor(
            database,
            acting_user_id,
        )

        factor = _get_factor(
            database,
            factor_id,
        )

        database.execute(
            """
            DELETE FROM strategic_analysis_evidence
            WHERE analysis_type = 'SWOT'
              AND analysis_record_id = ?
            """,
            (factor_id,),
        )

        database.execute(
            """
            DELETE FROM swot_factors
            WHERE id = ?
            """,
            (factor_id,),
        )

        _audit(
            acting_user_id,
            "DELETE",
            "SWOT Factor",
            factor_id,
            (
                "Deleted SWOT factor: "
                f"{factor['factor_name']}"
            ),
        )

        database.commit()

        return {
            "id": factor_id,
            "deleted": True,
        }

    except Exception:
        _rollback(database)
        raise
