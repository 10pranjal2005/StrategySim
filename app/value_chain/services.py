
"""
StrategySim - Value Chain Analysis Services

Provides:
- Value Chain assessment CRUD
- Primary and Support activity CRUD
- Activity validation
- Strategic importance and cost contribution handling
- Evidence associations
- Transactional audit logging

All mutations are transactional. Deleting an assessment or activity
removes its evidence associations, never the underlying evidence records.
"""

from app.database.connection import get_db
from app.services.audit_service import record_audit_log


# =========================================================
# CONSTANTS
# =========================================================

ACTIVITY_CATEGORIES = (
    "Primary",
    "Support",
)

ANALYSIS_TYPE = "VALUE_CHAIN"


# =========================================================
# EXCEPTIONS
# =========================================================

class ValueChainError(Exception):
    """Base exception for Value Chain operations."""


class ValueChainValidationError(ValueChainError):
    """Raised when input validation fails."""


class ValueChainNotFoundError(ValueChainError):
    """Raised when an assessment or activity does not exist."""


class ValueChainPermissionError(ValueChainError):
    """Raised when the acting user is unavailable or inactive."""


class ValueChainDuplicateError(ValueChainError):
    """Raised when a duplicate record is detected."""


# =========================================================
# VALIDATION HELPERS
# =========================================================

def _positive_id(value, field="ID"):
    try:
        result = int(value)
    except (TypeError, ValueError):
        raise ValueChainValidationError(
            f"{field} must be a valid positive integer."
        )

    if result <= 0:
        raise ValueChainValidationError(
            f"{field} must be greater than zero."
        )

    return result


def _required_text(value, field, max_length=200):
    if not isinstance(value, str):
        raise ValueChainValidationError(
            f"{field} is required."
        )

    result = value.strip()

    if not result:
        raise ValueChainValidationError(
            f"{field} is required."
        )

    if len(result) > max_length:
        raise ValueChainValidationError(
            f"{field} cannot exceed {max_length} characters."
        )

    return result


def _optional_text(value, field, max_length=2000):
    if value is None:
        return None

    if not isinstance(value, str):
        raise ValueChainValidationError(
            f"{field} must be text."
        )

    result = value.strip()

    if not result:
        return None

    if len(result) > max_length:
        raise ValueChainValidationError(
            f"{field} cannot exceed {max_length} characters."
        )

    return result


def _validate_category(value):
    if value not in ACTIVITY_CATEGORIES:
        raise ValueChainValidationError(
            "Activity category must be Primary or Support."
        )

    return value


def _validate_importance(value):
    if value is None or value == "":
        return None

    try:
        result = int(value)
    except (TypeError, ValueError):
        raise ValueChainValidationError(
            "Strategic importance must be an integer from 1 to 5."
        )

    if result < 1 or result > 5:
        raise ValueChainValidationError(
            "Strategic importance must be between 1 and 5."
        )

    return result


def _validate_cost(value):
    if value is None or value == "":
        return None

    try:
        result = float(value)
    except (TypeError, ValueError):
        raise ValueChainValidationError(
            "Cost contribution must be a valid number."
        )

    if result < 0:
        raise ValueChainValidationError(
            "Cost contribution cannot be negative."
        )

    return result


def _validate_date(value):
    if value is None or value == "":
        return None

    from datetime import date

    if not isinstance(value, str):
        raise ValueChainValidationError(
            "Assessment date must use YYYY-MM-DD format."
        )

    try:
        date.fromisoformat(value)
    except ValueError:
        raise ValueChainValidationError(
            "Assessment date must use YYYY-MM-DD format."
        )

    return value


# =========================================================
# COMMON DATABASE HELPERS
# =========================================================

def _validate_actor(db, acting_user_id):
    acting_user_id = _positive_id(
        acting_user_id,
        "Acting user ID"
    )

    user = db.execute(
        """
        SELECT id, is_active
        FROM users
        WHERE id = ?
        """,
        (acting_user_id,)
    ).fetchone()

    if user is None or not user["is_active"]:
        raise ValueChainPermissionError(
            "The acting user does not exist or is inactive."
        )

    return acting_user_id


def _validate_company(db, company_id):
    company_id = _positive_id(
        company_id,
        "Company ID"
    )

    company = db.execute(
        """
        SELECT id
        FROM companies
        WHERE id = ?
        """,
        (company_id,)
    ).fetchone()

    if company is None:
        raise ValueChainNotFoundError(
            "The selected company does not exist."
        )

    return company_id


def _validate_evidence(db, evidence_id):
    if evidence_id is None or evidence_id == "":
        return None

    evidence_id = _positive_id(
        evidence_id,
        "Evidence ID"
    )

    evidence = db.execute(
        """
        SELECT id
        FROM evidence
        WHERE id = ?
        """,
        (evidence_id,)
    ).fetchone()

    if evidence is None:
        raise ValueChainNotFoundError(
            "The selected evidence record does not exist."
        )

    return evidence_id


def _get_assessment_or_raise(db, assessment_id):
    assessment_id = _positive_id(
        assessment_id,
        "Assessment ID"
    )

    assessment = db.execute(
        """
        SELECT id
        FROM value_chain_assessments
        WHERE id = ?
        """,
        (assessment_id,)
    ).fetchone()

    if assessment is None:
        raise ValueChainNotFoundError(
            "Value Chain assessment not found."
        )

    return assessment_id


def _get_activity_or_raise(db, activity_id):
    activity_id = _positive_id(
        activity_id,
        "Activity ID"
    )

    activity = db.execute(
        """
        SELECT id, assessment_id
        FROM value_chain_activities
        WHERE id = ?
        """,
        (activity_id,)
    ).fetchone()

    if activity is None:
        raise ValueChainNotFoundError(
            "Value Chain activity not found."
        )

    return activity


def _audit(db, acting_user_id, action, entity_type,
           entity_id, description):

    record_audit_log(
        user_id=acting_user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        description=description,
        commit=False
    )


def _link_evidence(db, evidence_id, activity_id):
    """
    Create a shared evidence association.

    Existing identical associations are not duplicated.
    """

    if evidence_id is None:
        return

    existing = db.execute(
        """
        SELECT id
        FROM strategic_analysis_evidence
        WHERE evidence_id = ?
          AND analysis_type = ?
          AND analysis_record_id = ?
        """,
        (
            evidence_id,
            ANALYSIS_TYPE,
            activity_id
        )
    ).fetchone()

    if existing is None:
        db.execute(
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
                ANALYSIS_TYPE,
                activity_id
            )
        )


def _remove_evidence_links(db, activity_id):
    db.execute(
        """
        DELETE FROM strategic_analysis_evidence
        WHERE analysis_type = ?
          AND analysis_record_id = ?
        """,
        (
            ANALYSIS_TYPE,
            activity_id
        )
    )


def _remove_assessment_evidence_links(db, assessment_id):
    db.execute(
        """
        DELETE FROM strategic_analysis_evidence
        WHERE analysis_type = ?
          AND analysis_record_id IN (
              SELECT id
              FROM value_chain_activities
              WHERE assessment_id = ?
          )
        """,
        (
            ANALYSIS_TYPE,
            assessment_id
        )
    )


# =========================================================
# ASSESSMENT CRUD
# =========================================================

def create_value_chain_assessment(
    company_id,
    assessment_name,
    acting_user_id,
    assessment_date=None,
    summary=None
):
    db = get_db()

    try:
        acting_user_id = _validate_actor(
            db,
            acting_user_id
        )

        company_id = _validate_company(
            db,
            company_id
        )

        assessment_name = _required_text(
            assessment_name,
            "Assessment name",
            200
        )

        assessment_date = _validate_date(
            assessment_date
        )

        summary = _optional_text(
            summary,
            "Summary"
        )

        cursor = db.execute(
            """
            INSERT INTO value_chain_assessments (
                company_id,
                assessment_name,
                assessment_date,
                summary,
                created_by
            )
            VALUES (?, ?, COALESCE(?, CURRENT_TIMESTAMP), ?, ?)
            """,
            (
                company_id,
                assessment_name,
                assessment_date,
                summary,
                acting_user_id
            )
        )

        assessment_id = cursor.lastrowid

        _audit(
            db,
            acting_user_id,
            "CREATE",
            "VALUE_CHAIN_ASSESSMENT",
            assessment_id,
            f"Created Value Chain assessment: {assessment_name}"
        )

        db.commit()

        return assessment_id

    except Exception:
        db.rollback()
        raise


def get_value_chain_assessment(assessment_id):
    db = get_db()

    assessment_id = _positive_id(
        assessment_id,
        "Assessment ID"
    )

    assessment = db.execute(
        """
        SELECT
            a.*,
            c.name AS company_name,
            u.full_name AS created_by_name
        FROM value_chain_assessments a
        LEFT JOIN companies c
            ON c.id = a.company_id
        LEFT JOIN users u
            ON u.id = a.created_by
        WHERE a.id = ?
        """,
        (assessment_id,)
    ).fetchone()

    if assessment is None:
        raise ValueChainNotFoundError(
            "Value Chain assessment not found."
        )

    result = dict(assessment)

    result["activities"] = get_value_chain_activities(
        assessment_id
    )

    return result


def get_value_chain_assessments(
    company_id=None,
    limit=100,
    offset=0,
    search=None
):
    db = get_db()

    try:
        limit = int(limit)
        offset = int(offset)
    except (TypeError, ValueError):
        raise ValueChainValidationError(
            "Invalid pagination parameters."
        )

    if limit < 1 or limit > 500 or offset < 0:
        raise ValueChainValidationError(
            "Invalid pagination range."
        )

    query = """
        SELECT
            a.*,
            c.name AS company_name,
            u.full_name AS created_by_name,
            COUNT(v.id) AS activity_count
        FROM value_chain_assessments a
        LEFT JOIN companies c
            ON c.id = a.company_id
        LEFT JOIN users u
            ON u.id = a.created_by
        LEFT JOIN value_chain_activities v
            ON v.assessment_id = a.id
        WHERE 1 = 1
    """

    parameters = []

    if company_id is not None:
        company_id = _positive_id(
            company_id,
            "Company ID"
        )

        query += " AND a.company_id = ?"
        parameters.append(company_id)

    if search:
        search = _optional_text(
            search,
            "Search",
            200
        )

        if search:
            query += """
                AND (
                    a.assessment_name LIKE ?
                    OR c.name LIKE ?
                )
            """

            search_term = f"%{search}%"

            parameters.extend([
                search_term,
                search_term
            ])

    query += """
        GROUP BY a.id
        ORDER BY a.created_at DESC, a.id DESC
        LIMIT ? OFFSET ?
    """

    parameters.extend([
        limit,
        offset
    ])

    rows = db.execute(
        query,
        parameters
    ).fetchall()

    return [dict(row) for row in rows]


def update_value_chain_assessment(
    assessment_id,
    acting_user_id,
    updates
):
    db = get_db()

    try:
        assessment_id = _get_assessment_or_raise(
            db,
            assessment_id
        )

        acting_user_id = _validate_actor(
            db,
            acting_user_id
        )

        if not isinstance(updates, dict) or not updates:
            raise ValueChainValidationError(
                "No assessment updates were supplied."
            )

        allowed_fields = {
            "assessment_name",
            "assessment_date",
            "summary"
        }

        invalid_fields = set(updates) - allowed_fields

        if invalid_fields:
            raise ValueChainValidationError(
                "Unsupported assessment fields: "
                + ", ".join(sorted(invalid_fields))
            )

        validated = {}

        if "assessment_name" in updates:
            validated["assessment_name"] = _required_text(
                updates["assessment_name"],
                "Assessment name",
                200
            )

        if "assessment_date" in updates:
            validated["assessment_date"] = _validate_date(
                updates["assessment_date"]
            )

        if "summary" in updates:
            validated["summary"] = _optional_text(
                updates["summary"],
                "Summary"
            )

        if not validated:
            raise ValueChainValidationError(
                "No valid assessment fields were supplied."
            )

        assignments = ", ".join(
            f"{field} = ?" for field in validated
        )

        db.execute(
            f"""
            UPDATE value_chain_assessments
            SET {assignments}
            WHERE id = ?
            """,
            tuple(validated.values()) + (assessment_id,)
        )

        _audit(
            db,
            acting_user_id,
            "UPDATE",
            "VALUE_CHAIN_ASSESSMENT",
            assessment_id,
            "Updated Value Chain assessment."
        )

        db.commit()

        return True

    except Exception:
        db.rollback()
        raise


def delete_value_chain_assessment(
    assessment_id,
    acting_user_id
):
    db = get_db()

    try:
        assessment_id = _get_assessment_or_raise(
            db,
            assessment_id
        )

        acting_user_id = _validate_actor(
            db,
            acting_user_id
        )

        _remove_assessment_evidence_links(
            db,
            assessment_id
        )

        db.execute(
            """
            DELETE FROM value_chain_assessments
            WHERE id = ?
            """,
            (assessment_id,)
        )

        _audit(
            db,
            acting_user_id,
            "DELETE",
            "VALUE_CHAIN_ASSESSMENT",
            assessment_id,
            "Deleted Value Chain assessment and its activities."
        )

        db.commit()

        return True

    except Exception:
        db.rollback()
        raise


# =========================================================
# ACTIVITY CRUD
# =========================================================

def create_value_chain_activity(
    assessment_id,
    activity_category,
    activity_name,
    acting_user_id,
    description=None,
    cost_contribution=None,
    strategic_importance=None,
    competitive_advantage=None,
    evidence_id=None
):
    db = get_db()

    try:
        assessment_id = _get_assessment_or_raise(
            db,
            assessment_id
        )

        acting_user_id = _validate_actor(
            db,
            acting_user_id
        )

        activity_category = _validate_category(
            activity_category
        )

        activity_name = _required_text(
            activity_name,
            "Activity name",
            200
        )

        description = _optional_text(
            description,
            "Description"
        )

        cost_contribution = _validate_cost(
            cost_contribution
        )

        strategic_importance = _validate_importance(
            strategic_importance
        )

        competitive_advantage = _optional_text(
            competitive_advantage,
            "Competitive advantage"
        )

        evidence_id = _validate_evidence(
            db,
            evidence_id
        )

        cursor = db.execute(
            """
            INSERT INTO value_chain_activities (
                assessment_id,
                activity_category,
                activity_name,
                description,
                cost_contribution,
                strategic_importance,
                competitive_advantage
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                assessment_id,
                activity_category,
                activity_name,
                description,
                cost_contribution,
                strategic_importance,
                competitive_advantage
            )
        )

        activity_id = cursor.lastrowid

        if evidence_id is not None:
            _link_evidence(
                db,
                evidence_id,
                activity_id
            )

        _audit(
            db,
            acting_user_id,
            "CREATE",
            "VALUE_CHAIN_ACTIVITY",
            activity_id,
            f"Created {activity_category} activity: {activity_name}"
        )

        db.commit()

        return activity_id

    except Exception:
        db.rollback()
        raise


def get_value_chain_activity(activity_id):
    db = get_db()

    activity_id = _positive_id(
        activity_id,
        "Activity ID"
    )

    activity = db.execute(
        """
        SELECT
            a.*,
            e.id AS evidence_id,
            e.title AS evidence_title
        FROM value_chain_activities a
        LEFT JOIN strategic_analysis_evidence link
            ON link.analysis_record_id = a.id
            AND link.analysis_type = ?
        LEFT JOIN evidence e
            ON e.id = link.evidence_id
        WHERE a.id = ?
        """,
        (
            ANALYSIS_TYPE,
            activity_id
        )
    ).fetchone()

    if activity is None:
        raise ValueChainNotFoundError(
            "Value Chain activity not found."
        )

    return dict(activity)


def get_value_chain_activities(
    assessment_id,
    activity_category=None
):
    db = get_db()

    assessment_id = _get_assessment_or_raise(
        db,
        assessment_id
    )

    query = """
        SELECT
            a.*,
            e.id AS evidence_id,
            e.title AS evidence_title
        FROM value_chain_activities a
        LEFT JOIN strategic_analysis_evidence link
            ON link.analysis_record_id = a.id
            AND link.analysis_type = ?
        LEFT JOIN evidence e
            ON e.id = link.evidence_id
        WHERE a.assessment_id = ?
    """

    parameters = [
        ANALYSIS_TYPE,
        assessment_id
    ]

    if activity_category is not None:
        activity_category = _validate_category(
            activity_category
        )

        query += " AND a.activity_category = ?"
        parameters.append(activity_category)

    query += """
        ORDER BY
            CASE a.activity_category
                WHEN 'Primary' THEN 1
                WHEN 'Support' THEN 2
            END,
            a.id ASC
    """

    rows = db.execute(
        query,
        parameters
    ).fetchall()

    return [dict(row) for row in rows]


def update_value_chain_activity(
    activity_id,
    acting_user_id,
    updates,
    evidence_id=None
):
    db = get_db()

    try:
        activity = _get_activity_or_raise(
            db,
            activity_id
        )

        activity_id = activity["id"]

        acting_user_id = _validate_actor(
            db,
            acting_user_id
        )

        if not isinstance(updates, dict):
            raise ValueChainValidationError(
                "Activity updates must be supplied as a dictionary."
            )

        allowed_fields = {
            "activity_category",
            "activity_name",
            "description",
            "cost_contribution",
            "strategic_importance",
            "competitive_advantage"
        }

        invalid_fields = set(updates) - allowed_fields

        if invalid_fields:
            raise ValueChainValidationError(
                "Unsupported activity fields: "
                + ", ".join(sorted(invalid_fields))
            )

        validated = {}

        if "activity_category" in updates:
            validated["activity_category"] = _validate_category(
                updates["activity_category"]
            )

        if "activity_name" in updates:
            validated["activity_name"] = _required_text(
                updates["activity_name"],
                "Activity name",
                200
            )

        if "description" in updates:
            validated["description"] = _optional_text(
                updates["description"],
                "Description"
            )

        if "cost_contribution" in updates:
            validated["cost_contribution"] = _validate_cost(
                updates["cost_contribution"]
            )

        if "strategic_importance" in updates:
            validated["strategic_importance"] = _validate_importance(
                updates["strategic_importance"]
            )

        if "competitive_advantage" in updates:
            validated["competitive_advantage"] = _optional_text(
                updates["competitive_advantage"],
                "Competitive advantage"
            )

        validated_evidence_id = None

        if evidence_id is not None:
            validated_evidence_id = _validate_evidence(
                db,
                evidence_id
            )

        if not validated and evidence_id is None:
            raise ValueChainValidationError(
                "No activity updates were supplied."
            )

        if validated:
            assignments = ", ".join(
                f"{field} = ?" for field in validated
            )

            db.execute(
                f"""
                UPDATE value_chain_activities
                SET {assignments}
                WHERE id = ?
                """,
                tuple(validated.values()) + (activity_id,)
            )

        if evidence_id is not None:
            _remove_evidence_links(
                db,
                activity_id
            )

            if validated_evidence_id is not None:
                _link_evidence(
                    db,
                    validated_evidence_id,
                    activity_id
                )

        _audit(
            db,
            acting_user_id,
            "UPDATE",
            "VALUE_CHAIN_ACTIVITY",
            activity_id,
            "Updated Value Chain activity."
        )

        db.commit()

        return True

    except Exception:
        db.rollback()
        raise


def delete_value_chain_activity(
    activity_id,
    acting_user_id
):
    db = get_db()

    try:
        activity = _get_activity_or_raise(
            db,
            activity_id
        )

        activity_id = activity["id"]

        acting_user_id = _validate_actor(
            db,
            acting_user_id
        )

        _remove_evidence_links(
            db,
            activity_id
        )

        db.execute(
            """
            DELETE FROM value_chain_activities
            WHERE id = ?
            """,
            (activity_id,)
        )

        _audit(
            db,
            acting_user_id,
            "DELETE",
            "VALUE_CHAIN_ACTIVITY",
            activity_id,
            "Deleted Value Chain activity."
        )

        db.commit()

        return True

    except Exception:
        db.rollback()
        raise
