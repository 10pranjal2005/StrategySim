
import sqlite3

from app.database.connection import get_db
from app.services.audit_service import record_audit_log


# =========================================================
# CUSTOM EXCEPTIONS
# =========================================================

class CompetitorNotFoundError(Exception):
    """Raised when a competitor company does not exist."""


class TargetCompanyNotFoundError(Exception):
    """Raised when a target company does not exist."""


class CompetitorRelationshipNotFoundError(Exception):
    """Raised when a competitor relationship does not exist."""


class InvalidCompetitorDataError(Exception):
    """Raised when competitor relationship data is invalid."""


class DuplicateCompetitorRelationshipError(Exception):
    """Raised when the same relationship already exists."""


class InvalidCompetitorRelationshipError(Exception):
    """Raised when a relationship violates business rules."""


# =========================================================
# CONSTANTS
# =========================================================

MIN_COMPETITIVE_STRENGTH = 1
MAX_COMPETITIVE_STRENGTH = 5

MAX_RELATIONSHIP_NOTES_LENGTH = 2000


# =========================================================
# INTERNAL VALIDATION HELPERS
# =========================================================

def _validate_positive_id(value, field_name):
    """
    Validate that an identifier is a positive integer.
    Boolean values are explicitly rejected.
    """

    if isinstance(value, bool):
        raise InvalidCompetitorDataError(
            f"{field_name} must be a positive integer."
        )

    try:
        converted_value = int(value)
    except (TypeError, ValueError):
        raise InvalidCompetitorDataError(
            f"{field_name} must be a positive integer."
        )

    if converted_value <= 0 or str(converted_value) != str(value).strip():
        raise InvalidCompetitorDataError(
            f"{field_name} must be a positive integer."
        )

    return converted_value


def _validate_competitive_strength(value):
    """
    Validate competitive strength.

    Accepted values:
    - None
    - Integer between 1 and 5
    """

    if value is None or value == "":
        return None

    if isinstance(value, bool):
        raise InvalidCompetitorDataError(
            "Competitive strength must be an integer between 1 and 5."
        )

    try:
        strength = int(value)
    except (TypeError, ValueError):
        raise InvalidCompetitorDataError(
            "Competitive strength must be an integer between 1 and 5."
        )

    if str(strength) != str(value).strip():
        raise InvalidCompetitorDataError(
            "Competitive strength must be an integer between 1 and 5."
        )

    if not MIN_COMPETITIVE_STRENGTH <= strength <= MAX_COMPETITIVE_STRENGTH:
        raise InvalidCompetitorDataError(
            "Competitive strength must be between 1 and 5."
        )

    return strength


def _validate_notes(notes):
    """
    Validate optional relationship notes.
    """

    if notes is None:
        return None

    if not isinstance(notes, str):
        raise InvalidCompetitorDataError(
            "Relationship notes must be text."
        )

    cleaned_notes = notes.strip()

    if len(cleaned_notes) > MAX_RELATIONSHIP_NOTES_LENGTH:
        raise InvalidCompetitorDataError(
            f"Relationship notes cannot exceed "
            f"{MAX_RELATIONSHIP_NOTES_LENGTH} characters."
        )

    return cleaned_notes or None


# =========================================================
# INTERNAL COMPANY VALIDATION
# =========================================================

def _get_and_validate_companies(
    cursor,
    target_company_id,
    competitor_id
):
    """
    Retrieve and validate the target and competitor companies.

    Business rules:
    - Target must have company_type = Target.
    - Competitor must have company_type = Competitor.
    - Both must belong to the same industry.
    - A company cannot compete against itself.
    """

    if target_company_id == competitor_id:
        raise InvalidCompetitorRelationshipError(
            "A company cannot be linked as its own competitor."
        )

    cursor.execute(
        """
        SELECT
            id,
            name,
            industry_id,
            company_type,
            is_demo
        FROM companies
        WHERE id = ?
        """,
        (target_company_id,)
    )

    target_company = cursor.fetchone()

    if target_company is None:
        raise TargetCompanyNotFoundError(
            "The selected target company does not exist."
        )

    if target_company["company_type"] != "Target":
        raise InvalidCompetitorRelationshipError(
            "The selected company must have company type 'Target'."
        )

    cursor.execute(
        """
        SELECT
            id,
            name,
            industry_id,
            company_type,
            is_demo
        FROM companies
        WHERE id = ?
        """,
        (competitor_id,)
    )

    competitor = cursor.fetchone()

    if competitor is None:
        raise CompetitorNotFoundError(
            "The selected competitor does not exist."
        )

    if competitor["company_type"] != "Competitor":
        raise InvalidCompetitorRelationshipError(
            "The selected company must have company type 'Competitor'."
        )

    if target_company["industry_id"] != competitor["industry_id"]:
        raise InvalidCompetitorRelationshipError(
            "The target company and competitor must belong to the same industry."
        )

    return target_company, competitor


# =========================================================
# COMPETITOR DIRECTORY
# =========================================================

def get_competitors(
    search=None,
    industry_id=None,
    limit=100,
    offset=0
):
    """
    Retrieve competitor companies.

    Supports:
    - Search by competitor name
    - Industry filtering
    - Pagination
    """

    if isinstance(limit, bool) or not isinstance(limit, int):
        raise InvalidCompetitorDataError(
            "Limit must be an integer."
        )

    if isinstance(offset, bool) or not isinstance(offset, int):
        raise InvalidCompetitorDataError(
            "Offset must be an integer."
        )

    if not 1 <= limit <= 500:
        raise InvalidCompetitorDataError(
            "Limit must be between 1 and 500."
        )

    if offset < 0:
        raise InvalidCompetitorDataError(
            "Offset cannot be negative."
        )

    conditions = ["c.company_type = 'Competitor'"]
    parameters = []

    if search is not None:
        if not isinstance(search, str):
            raise InvalidCompetitorDataError(
                "Search term must be text."
            )

        search = search.strip()

        if search:
            conditions.append("c.name LIKE ?")
            parameters.append(f"%{search}%")

    if industry_id is not None:
        industry_id = _validate_positive_id(
            industry_id,
            "Industry ID"
        )

        conditions.append("c.industry_id = ?")
        parameters.append(industry_id)

    where_clause = " AND ".join(conditions)

    db = get_db()
    cursor = db.cursor()

    cursor.execute(
        f"""
        SELECT
            c.id,
            c.industry_id,
            i.name AS industry_name,
            c.name,
            c.company_type,
            c.description,
            c.headquarters,
            c.website,
            c.annual_revenue,
            c.employee_count,
            c.market_share,
            c.founded_year,
            c.is_demo,
            c.created_at,
            c.updated_at,
            COUNT(DISTINCT cr.id) AS relationship_count
        FROM companies c
        JOIN industries i
            ON i.id = c.industry_id
        LEFT JOIN competitor_relationships cr
            ON cr.competitor_id = c.id
        WHERE {where_clause}
        GROUP BY c.id
        ORDER BY c.name COLLATE NOCASE ASC
        LIMIT ? OFFSET ?
        """,
        parameters + [limit, offset]
    )

    competitors = [dict(row) for row in cursor.fetchall()]

    cursor.execute(
        f"""
        SELECT COUNT(*)
        FROM companies c
        WHERE {where_clause}
        """,
        parameters
    )

    total_count = cursor.fetchone()[0]

    return {
        "items": competitors,
        "total": total_count,
        "limit": limit,
        "offset": offset
    }


# =========================================================
# COMPETITOR PROFILE
# =========================================================

def get_competitor_details(competitor_id):
    """
    Retrieve a competitor profile and its associated
    target-company relationships.
    """

    competitor_id = _validate_positive_id(
        competitor_id,
        "Competitor ID"
    )

    db = get_db()
    cursor = db.cursor()

    cursor.execute(
        """
        SELECT
            c.id,
            c.industry_id,
            i.name AS industry_name,
            c.name,
            c.company_type,
            c.description,
            c.headquarters,
            c.website,
            c.annual_revenue,
            c.employee_count,
            c.market_share,
            c.founded_year,
            c.is_demo,
            c.created_at,
            c.updated_at
        FROM companies c
        JOIN industries i
            ON i.id = c.industry_id
        WHERE c.id = ?
          AND c.company_type = 'Competitor'
        """,
        (competitor_id,)
    )

    competitor = cursor.fetchone()

    if competitor is None:
        raise CompetitorNotFoundError(
            "The requested competitor does not exist."
        )

    cursor.execute(
        """
        SELECT
            cr.id AS relationship_id,
            cr.company_id AS target_company_id,
            target.name AS target_company_name,
            target.industry_id,
            cr.competitive_strength,
            cr.notes,
            cr.created_at
        FROM competitor_relationships cr
        JOIN companies target
            ON target.id = cr.company_id
        WHERE cr.competitor_id = ?
        ORDER BY target.name COLLATE NOCASE ASC
        """,
        (competitor_id,)
    )

    relationships = [
        dict(row)
        for row in cursor.fetchall()
    ]

    result = dict(competitor)

    result["relationships"] = relationships
    result["relationship_count"] = len(relationships)

    return result


# =========================================================
# TARGET COMPANY COMPETITOR RELATIONSHIPS
# =========================================================

def get_company_competitors(target_company_id):
    """
    Retrieve all competitors linked to a target company.
    """

    target_company_id = _validate_positive_id(
        target_company_id,
        "Target company ID"
    )

    db = get_db()
    cursor = db.cursor()

    cursor.execute(
        """
        SELECT
            id,
            name,
            company_type
        FROM companies
        WHERE id = ?
        """,
        (target_company_id,)
    )

    target_company = cursor.fetchone()

    if target_company is None:
        raise TargetCompanyNotFoundError(
            "The requested target company does not exist."
        )

    if target_company["company_type"] != "Target":
        raise InvalidCompetitorRelationshipError(
            "The selected company is not a target company."
        )

    cursor.execute(
        """
        SELECT
            cr.id AS relationship_id,
            cr.company_id AS target_company_id,
            cr.competitor_id,
            competitor.name AS competitor_name,
            competitor.description AS competitor_description,
            competitor.headquarters,
            competitor.website,
            competitor.annual_revenue,
            competitor.employee_count,
            competitor.market_share,
            competitor.founded_year,
            competitor.is_demo,
            cr.competitive_strength,
            cr.notes,
            cr.created_at
        FROM competitor_relationships cr
        JOIN companies competitor
            ON competitor.id = cr.competitor_id
        WHERE cr.company_id = ?
        ORDER BY competitor.name COLLATE NOCASE ASC
        """,
        (target_company_id,)
    )

    relationships = [
        dict(row)
        for row in cursor.fetchall()
    ]

    return {
        "target_company": dict(target_company),
        "items": relationships,
        "total": len(relationships)
    }


# =========================================================
# RELATIONSHIP CREATION
# =========================================================

def create_competitor_relationship(
    target_company_id,
    competitor_id,
    acting_user_id,
    competitive_strength=None,
    notes=None
):
    """
    Create a relationship between a target company
    and a competitor.

    The relationship and audit record are committed
    together in a single transaction.
    """

    target_company_id = _validate_positive_id(
        target_company_id,
        "Target company ID"
    )

    competitor_id = _validate_positive_id(
        competitor_id,
        "Competitor ID"
    )

    acting_user_id = _validate_positive_id(
        acting_user_id,
        "Acting user ID"
    )

    competitive_strength = _validate_competitive_strength(
        competitive_strength
    )

    notes = _validate_notes(notes)

    db = get_db()
    cursor = db.cursor()

    try:
        cursor.execute("BEGIN IMMEDIATE")

        target_company, competitor = _get_and_validate_companies(
            cursor,
            target_company_id,
            competitor_id
        )

        cursor.execute(
            """
            SELECT id
            FROM competitor_relationships
            WHERE company_id = ?
              AND competitor_id = ?
            """,
            (target_company_id, competitor_id)
        )

        if cursor.fetchone() is not None:
            raise DuplicateCompetitorRelationshipError(
                "This competitor is already linked to the target company."
            )

        cursor.execute(
            """
            INSERT INTO competitor_relationships (
                company_id,
                competitor_id,
                competitive_strength,
                notes
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                target_company_id,
                competitor_id,
                competitive_strength,
                notes
            )
        )

        relationship_id = cursor.lastrowid

        record_audit_log(
            user_id=acting_user_id,
            action="CREATE",
            entity_type="competitor_relationship",
            entity_id=relationship_id,
            description=(
                f"Linked competitor '{competitor['name']}' "
                f"to target company '{target_company['name']}'."
            ),
            commit=False
        )

        db.commit()

        return relationship_id

    except Exception:
        db.rollback()
        raise


# =========================================================
# RELATIONSHIP UPDATE
# =========================================================

def update_competitor_relationship(
    relationship_id,
    acting_user_id,
    competitive_strength=None,
    notes=None
):
    """
    Update the competitive strength and notes of
    an existing competitor relationship.
    """

    relationship_id = _validate_positive_id(
        relationship_id,
        "Relationship ID"
    )

    acting_user_id = _validate_positive_id(
        acting_user_id,
        "Acting user ID"
    )

    competitive_strength = _validate_competitive_strength(
        competitive_strength
    )

    notes = _validate_notes(notes)

    db = get_db()
    cursor = db.cursor()

    try:
        cursor.execute("BEGIN IMMEDIATE")

        cursor.execute(
            """
            SELECT
                cr.id,
                target.name AS target_company_name,
                competitor.name AS competitor_name
            FROM competitor_relationships cr
            JOIN companies target
                ON target.id = cr.company_id
            JOIN companies competitor
                ON competitor.id = cr.competitor_id
            WHERE cr.id = ?
            """,
            (relationship_id,)
        )

        relationship = cursor.fetchone()

        if relationship is None:
            raise CompetitorRelationshipNotFoundError(
                "The requested competitor relationship does not exist."
            )

        cursor.execute(
            """
            UPDATE competitor_relationships
            SET
                competitive_strength = ?,
                notes = ?
            WHERE id = ?
            """,
            (
                competitive_strength,
                notes,
                relationship_id
            )
        )

        record_audit_log(
            user_id=acting_user_id,
            action="UPDATE",
            entity_type="competitor_relationship",
            entity_id=relationship_id,
            description=(
                f"Updated competitor relationship between "
                f"'{relationship['target_company_name']}' and "
                f"'{relationship['competitor_name']}'."
            ),
            commit=False
        )

        db.commit()

        return relationship_id

    except Exception:
        db.rollback()
        raise


# =========================================================
# RELATIONSHIP DELETION
# =========================================================

def delete_competitor_relationship(
    relationship_id,
    acting_user_id
):
    """
    Delete only the relationship record.

    The target company and competitor company remain
    untouched.
    """

    relationship_id = _validate_positive_id(
        relationship_id,
        "Relationship ID"
    )

    acting_user_id = _validate_positive_id(
        acting_user_id,
        "Acting user ID"
    )

    db = get_db()
    cursor = db.cursor()

    try:
        cursor.execute("BEGIN IMMEDIATE")

        cursor.execute(
            """
            SELECT
                cr.id,
                target.name AS target_company_name,
                competitor.name AS competitor_name
            FROM competitor_relationships cr
            JOIN companies target
                ON target.id = cr.company_id
            JOIN companies competitor
                ON competitor.id = cr.competitor_id
            WHERE cr.id = ?
            """,
            (relationship_id,)
        )

        relationship = cursor.fetchone()

        if relationship is None:
            raise CompetitorRelationshipNotFoundError(
                "The requested competitor relationship does not exist."
            )

        cursor.execute(
            """
            DELETE FROM competitor_relationships
            WHERE id = ?
            """,
            (relationship_id,)
        )

        record_audit_log(
            user_id=acting_user_id,
            action="DELETE",
            entity_type="competitor_relationship",
            entity_id=relationship_id,
            description=(
                f"Removed competitor relationship between "
                f"'{relationship['target_company_name']}' and "
                f"'{relationship['competitor_name']}'."
            ),
            commit=False
        )

        db.commit()

        return True

    except Exception:
        db.rollback()
        raise
