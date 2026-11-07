
"""
StrategySim - Porter's Five Forces Analysis Service.

Handles:
- Five Forces assessment CRUD
- Indicator CRUD
- Force-level weighted score calculation
- Overall assessment score calculation
- Evidence reference validation
- Transactional audit logging

The service uses the existing database schema without altering it.
"""

import sqlite3

from app.database.connection import get_db
from app.services.audit_service import record_audit_log


# =========================================================
# CONSTANTS
# =========================================================

FORCES = (
    "Buyer Power",
    "Supplier Power",
    "Competitive Rivalry",
    "Threat of Substitution",
    "Threat of New Entrants",
)

MIN_SCORE = 1
MAX_SCORE = 5

MAX_ASSESSMENT_NAME_LENGTH = 150
MAX_SUMMARY_LENGTH = 5000
MAX_INDICATOR_NAME_LENGTH = 200
MAX_EXPLANATION_LENGTH = 5000


# =========================================================
# CUSTOM EXCEPTIONS
# =========================================================

class FiveForcesError(Exception):
    """Base exception for Five Forces operations."""


class FiveForcesValidationError(FiveForcesError):
    """Raised when supplied data is invalid."""


class FiveForcesNotFoundError(FiveForcesError):
    """Raised when an assessment or indicator does not exist."""


class FiveForcesPermissionError(FiveForcesError):
    """Raised when the acting user is not permitted to perform an operation."""


class FiveForcesDuplicateError(FiveForcesError):
    """Raised when duplicate data is detected."""


# =========================================================
# VALIDATION HELPERS
# =========================================================

def _positive_id(value, field_name):
    if isinstance(value, bool):
        raise FiveForcesValidationError(
            f"{field_name} must be a positive integer."
        )

    try:
        converted = int(value)
    except (TypeError, ValueError):
        raise FiveForcesValidationError(
            f"{field_name} must be a positive integer."
        )

    if converted <= 0 or str(converted) != str(value).strip():
        raise FiveForcesValidationError(
            f"{field_name} must be a positive integer."
        )

    return converted


def _required_text(value, field_name, maximum):
    if not isinstance(value, str):
        raise FiveForcesValidationError(
            f"{field_name} must be text."
        )

    value = value.strip()

    if not value:
        raise FiveForcesValidationError(
            f"{field_name} cannot be empty."
        )

    if len(value) > maximum:
        raise FiveForcesValidationError(
            f"{field_name} cannot exceed {maximum} characters."
        )

    return value


def _optional_text(value, field_name, maximum):
    if value is None:
        return None

    if not isinstance(value, str):
        raise FiveForcesValidationError(
            f"{field_name} must be text."
        )

    value = value.strip()

    if not value:
        return None

    if len(value) > maximum:
        raise FiveForcesValidationError(
            f"{field_name} cannot exceed {maximum} characters."
        )

    return value


def _validate_score(value):
    if isinstance(value, bool):
        raise FiveForcesValidationError(
            "Indicator score must be between 1 and 5."
        )

    try:
        score = int(value)
    except (TypeError, ValueError):
        raise FiveForcesValidationError(
            "Indicator score must be a whole number between 1 and 5."
        )

    if str(score) != str(value).strip() or not MIN_SCORE <= score <= MAX_SCORE:
        raise FiveForcesValidationError(
            "Indicator score must be a whole number between 1 and 5."
        )

    return score


def _validate_weight(value):
    if isinstance(value, bool):
        raise FiveForcesValidationError(
            "Indicator weight must be a positive number."
        )

    try:
        weight = float(value)
    except (TypeError, ValueError):
        raise FiveForcesValidationError(
            "Indicator weight must be a positive number."
        )

    if weight <= 0:
        raise FiveForcesValidationError(
            "Indicator weight must be greater than zero."
        )

    return weight


def _validate_force(force_name):
    force_name = _required_text(
        force_name,
        "Force name",
        100
    )

    if force_name not in FORCES:
        raise FiveForcesValidationError(
            "Invalid force name. Select one of the five supported forces."
        )

    return force_name


def _validate_date(value):
    if value is None or value == "":
        return None

    if not isinstance(value, str):
        raise FiveForcesValidationError(
            "Assessment date must use YYYY-MM-DD format."
        )

    from datetime import date

    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        raise FiveForcesValidationError(
            "Assessment date must use YYYY-MM-DD format."
        )

    if parsed.isoformat() != value:
        raise FiveForcesValidationError(
            "Assessment date must use YYYY-MM-DD format."
        )

    return value


def _validate_actor(database, acting_user_id):
    acting_user_id = _positive_id(
        acting_user_id,
        "Acting user ID"
    )

    user = database.execute(
        """
        SELECT id, role, is_active
        FROM users
        WHERE id = ?
        """,
        (acting_user_id,)
    ).fetchone()

    if user is None or not user["is_active"]:
        raise FiveForcesPermissionError(
            "The acting user does not exist or is inactive."
        )

    if user["role"] not in ("Administrator", "Analyst"):
        raise FiveForcesPermissionError(
            "Only Administrators and Analysts can modify Five Forces data."
        )

    return acting_user_id


def _validate_company(database, company_id):
    company_id = _positive_id(company_id, "Company ID")

    company = database.execute(
        """
        SELECT id
        FROM companies
        WHERE id = ?
        """,
        (company_id,)
    ).fetchone()

    if company is None:
        raise FiveForcesNotFoundError(
            "The selected company does not exist."
        )

    return company_id


def _validate_evidence(database, evidence_id):
    if evidence_id in (None, ""):
        return None

    evidence_id = _positive_id(
        evidence_id,
        "Evidence ID"
    )

    evidence = database.execute(
        """
        SELECT id
        FROM evidence
        WHERE id = ?
        """,
        (evidence_id,)
    ).fetchone()

    if evidence is None:
        raise FiveForcesNotFoundError(
            "The selected evidence record does not exist."
        )

    return evidence_id


# =========================================================
# INTERNAL DATABASE HELPERS
# =========================================================

def _get_assessment_or_raise(database, assessment_id):
    assessment = database.execute(
        """
        SELECT *
        FROM five_forces_assessments
        WHERE id = ?
        """,
        (assessment_id,)
    ).fetchone()

    if assessment is None:
        raise FiveForcesNotFoundError(
            "The requested Five Forces assessment does not exist."
        )

    return assessment


def _get_indicator_or_raise(database, indicator_id):
    indicator = database.execute(
        """
        SELECT *
        FROM five_forces_indicators
        WHERE id = ?
        """,
        (indicator_id,)
    ).fetchone()

    if indicator is None:
        raise FiveForcesNotFoundError(
            "The requested Five Forces indicator does not exist."
        )

    return indicator


def _calculate_scores(database, assessment_id):
    """
    Calculate weighted scores for each force.

    Force score:
        SUM(score * weight) / SUM(weight)

    Overall score:
        Average of all five force scores.

    The overall score remains NULL until every force
    has at least one indicator.
    """

    force_scores = {}

    for force in FORCES:
        result = database.execute(
            """
            SELECT
                SUM(score * weight) AS weighted_total,
                SUM(weight) AS total_weight
            FROM five_forces_indicators
            WHERE assessment_id = ?
              AND force_name = ?
            """,
            (assessment_id, force)
        ).fetchone()

        if result["total_weight"] is None:
            force_scores[force] = None
        else:
            force_scores[force] = round(
                result["weighted_total"] / result["total_weight"],
                2
            )

    if all(force_scores[force] is not None for force in FORCES):
        overall_score = round(
            sum(force_scores.values()) / len(FORCES),
            2
        )
    else:
        overall_score = None

    database.execute(
        """
        UPDATE five_forces_assessments
        SET
            buyer_power_score = ?,
            supplier_power_score = ?,
            competitive_rivalry_score = ?,
            threat_of_substitution_score = ?,
            threat_of_new_entrants_score = ?,
            overall_score = ?
        WHERE id = ?
        """,
        (
            force_scores["Buyer Power"],
            force_scores["Supplier Power"],
            force_scores["Competitive Rivalry"],
            force_scores["Threat of Substitution"],
            force_scores["Threat of New Entrants"],
            overall_score,
            assessment_id
        )
    )

    return {
        "force_scores": force_scores,
        "overall_score": overall_score,
        "is_complete": overall_score is not None
    }


def _audit(
    acting_user_id,
    action,
    entity_type,
    entity_id,
    description
):
    record_audit_log(
        user_id=acting_user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        description=description,
        commit=False
    )


# =========================================================
# ASSESSMENT CRUD
# =========================================================

def create_five_forces_assessment(
    company_id,
    assessment_name,
    acting_user_id,
    assessment_date=None,
    summary=None
):
    database = get_db()

    company_id = _validate_company(database, company_id)
    acting_user_id = _validate_actor(
        database,
        acting_user_id
    )

    assessment_name = _required_text(
        assessment_name,
        "Assessment name",
        MAX_ASSESSMENT_NAME_LENGTH
    )

    assessment_date = _validate_date(assessment_date)
    summary = _optional_text(
        summary,
        "Summary",
        MAX_SUMMARY_LENGTH
    )

    try:
        database.execute("BEGIN IMMEDIATE")

        cursor = database.execute(
            """
            INSERT INTO five_forces_assessments (
                company_id,
                assessment_name,
                assessment_date,
                summary,
                created_by
            )
            VALUES (?, ?, ?, ?, ?)
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
            acting_user_id,
            "FIVE_FORCES_ASSESSMENT_CREATED",
            "Five Forces Assessment",
            assessment_id,
            f"Created Five Forces assessment '{assessment_name}'."
        )

        database.commit()

        return get_five_forces_assessment(assessment_id)

    except Exception:
        database.rollback()
        raise


def get_five_forces_assessment(assessment_id):
    assessment_id = _positive_id(
        assessment_id,
        "Assessment ID"
    )

    database = get_db()

    row = database.execute(
        """
        SELECT
            a.*,
            c.name AS company_name,
            u.full_name AS created_by_name
        FROM five_forces_assessments a
        JOIN companies c ON c.id = a.company_id
        LEFT JOIN users u ON u.id = a.created_by
        WHERE a.id = ?
        """,
        (assessment_id,)
    ).fetchone()

    if row is None:
        return None

    assessment = dict(row)

    indicators = database.execute(
        """
        SELECT
            i.*,
            e.title AS evidence_title
        FROM five_forces_indicators i
        LEFT JOIN evidence e ON e.id = i.evidence_id
        WHERE i.assessment_id = ?
        ORDER BY i.force_name, i.id
        """,
        (assessment_id,)
    ).fetchall()

    assessment["indicators"] = [
        dict(indicator) for indicator in indicators
    ]

    assessment["score_summary"] = {
        "force_scores": {
            "Buyer Power": assessment["buyer_power_score"],
            "Supplier Power": assessment["supplier_power_score"],
            "Competitive Rivalry": assessment["competitive_rivalry_score"],
            "Threat of Substitution": assessment["threat_of_substitution_score"],
            "Threat of New Entrants": assessment["threat_of_new_entrants_score"]
        },
        "overall_score": assessment["overall_score"],
        "is_complete": assessment["overall_score"] is not None
    }

    return assessment


def get_five_forces_assessments(
    company_id=None,
    limit=100,
    offset=0,
    search=None
):
    database = get_db()

    if isinstance(limit, bool) or not isinstance(limit, int):
        raise FiveForcesValidationError(
            "Limit must be an integer."
        )

    if isinstance(offset, bool) or not isinstance(offset, int):
        raise FiveForcesValidationError(
            "Offset must be an integer."
        )

    if not 1 <= limit <= 500:
        raise FiveForcesValidationError(
            "Limit must be between 1 and 500."
        )

    if offset < 0:
        raise FiveForcesValidationError(
            "Offset cannot be negative."
        )

    conditions = []
    parameters = []

    if company_id is not None:
        company_id = _positive_id(company_id, "Company ID")
        conditions.append("a.company_id = ?")
        parameters.append(company_id)

    if search:
        search = _required_text(
            search,
            "Search term",
            150
        )
        conditions.append(
            "(a.assessment_name LIKE ? OR c.name LIKE ?)"
        )
        parameters.extend([
            f"%{search}%",
            f"%{search}%"
        ])

    where_clause = (
        "WHERE " + " AND ".join(conditions)
        if conditions else ""
    )

    rows = database.execute(
        f"""
        SELECT
            a.*,
            c.name AS company_name,
            u.full_name AS created_by_name
        FROM five_forces_assessments a
        JOIN companies c ON c.id = a.company_id
        LEFT JOIN users u ON u.id = a.created_by
        {where_clause}
        ORDER BY a.created_at DESC, a.id DESC
        LIMIT ? OFFSET ?
        """,
        (*parameters, limit, offset)
    ).fetchall()

    return [dict(row) for row in rows]


def update_five_forces_assessment(
    assessment_id,
    acting_user_id,
    updates
):
    assessment_id = _positive_id(
        assessment_id,
        "Assessment ID"
    )

    if not isinstance(updates, dict) or not updates:
        raise FiveForcesValidationError(
            "Provide at least one assessment field to update."
        )

    allowed_fields = {
        "assessment_name",
        "assessment_date",
        "summary"
    }

    if not set(updates).issubset(allowed_fields):
        raise FiveForcesValidationError(
            "One or more assessment fields cannot be updated."
        )

    database = get_db()
    acting_user_id = _validate_actor(
        database,
        acting_user_id
    )

    _get_assessment_or_raise(database, assessment_id)

    values = {}

    if "assessment_name" in updates:
        values["assessment_name"] = _required_text(
            updates["assessment_name"],
            "Assessment name",
            MAX_ASSESSMENT_NAME_LENGTH
        )

    if "assessment_date" in updates:
        values["assessment_date"] = _validate_date(
            updates["assessment_date"]
        )

    if "summary" in updates:
        values["summary"] = _optional_text(
            updates["summary"],
            "Summary",
            MAX_SUMMARY_LENGTH
        )

    assignments = ", ".join(
        f"{field} = ?" for field in values
    )

    try:
        database.execute("BEGIN IMMEDIATE")

        database.execute(
            f"""
            UPDATE five_forces_assessments
            SET {assignments}
            WHERE id = ?
            """,
            (*values.values(), assessment_id)
        )

        _audit(
            acting_user_id,
            "FIVE_FORCES_ASSESSMENT_UPDATED",
            "Five Forces Assessment",
            assessment_id,
            f"Updated Five Forces assessment ID {assessment_id}."
        )

        database.commit()

        return get_five_forces_assessment(assessment_id)

    except Exception:
        database.rollback()
        raise


def delete_five_forces_assessment(
    assessment_id,
    acting_user_id
):
    assessment_id = _positive_id(
        assessment_id,
        "Assessment ID"
    )

    database = get_db()
    acting_user_id = _validate_actor(
        database,
        acting_user_id
    )

    assessment = _get_assessment_or_raise(
        database,
        assessment_id
    )

    try:
        database.execute("BEGIN IMMEDIATE")

        database.execute(
            """
            DELETE FROM strategic_analysis_evidence
            WHERE analysis_type = 'FIVE_FORCES'
              AND analysis_record_id IN (
                  SELECT id
                  FROM five_forces_indicators
                  WHERE assessment_id = ?
              )
            """,
            (assessment_id,)
        )

        database.execute(
            """
            DELETE FROM five_forces_assessments
            WHERE id = ?
            """,
            (assessment_id,)
        )

        _audit(
            acting_user_id,
            "FIVE_FORCES_ASSESSMENT_DELETED",
            "Five Forces Assessment",
            assessment_id,
            (
                f"Deleted Five Forces assessment "
                f"'{assessment['assessment_name']}'."
            )
        )

        database.commit()
        return True

    except Exception:
        database.rollback()
        raise


# =========================================================
# INDICATOR CRUD
# =========================================================

def create_five_forces_indicator(
    assessment_id,
    force_name,
    indicator_name,
    score,
    weight,
    acting_user_id,
    explanation=None,
    evidence_id=None
):
    assessment_id = _positive_id(
        assessment_id,
        "Assessment ID"
    )

    database = get_db()
    acting_user_id = _validate_actor(
        database,
        acting_user_id
    )

    force_name = _validate_force(force_name)

    indicator_name = _required_text(
        indicator_name,
        "Indicator name",
        MAX_INDICATOR_NAME_LENGTH
    )

    score = _validate_score(score)
    weight = _validate_weight(weight)

    explanation = _optional_text(
        explanation,
        "Explanation",
        MAX_EXPLANATION_LENGTH
    )

    evidence_id = _validate_evidence(
        database,
        evidence_id
    )

    _get_assessment_or_raise(database, assessment_id)

    try:
        database.execute("BEGIN IMMEDIATE")

        cursor = database.execute(
            """
            INSERT INTO five_forces_indicators (
                assessment_id,
                force_name,
                indicator_name,
                score,
                weight,
                explanation,
                evidence_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                assessment_id,
                force_name,
                indicator_name,
                score,
                weight,
                explanation,
                evidence_id
            )
        )

        indicator_id = cursor.lastrowid

        score_summary = _calculate_scores(
            database,
            assessment_id
        )

        _audit(
            acting_user_id,
            "FIVE_FORCES_INDICATOR_CREATED",
            "Five Forces Indicator",
            indicator_id,
            (
                f"Added indicator '{indicator_name}' "
                f"under {force_name}."
            )
        )

        database.commit()

        result = get_five_forces_indicator(indicator_id)
        result["score_summary"] = score_summary

        return result

    except Exception:
        database.rollback()
        raise


def get_five_forces_indicator(indicator_id):
    indicator_id = _positive_id(
        indicator_id,
        "Indicator ID"
    )

    database = get_db()

    row = database.execute(
        """
        SELECT
            i.*,
            e.title AS evidence_title
        FROM five_forces_indicators i
        LEFT JOIN evidence e ON e.id = i.evidence_id
        WHERE i.id = ?
        """,
        (indicator_id,)
    ).fetchone()

    return dict(row) if row else None


def get_five_forces_indicators(
    assessment_id,
    force_name=None
):
    assessment_id = _positive_id(
        assessment_id,
        "Assessment ID"
    )

    database = get_db()

    _get_assessment_or_raise(database, assessment_id)

    if force_name is not None:
        force_name = _validate_force(force_name)

        rows = database.execute(
            """
            SELECT
                i.*,
                e.title AS evidence_title
            FROM five_forces_indicators i
            LEFT JOIN evidence e ON e.id = i.evidence_id
            WHERE i.assessment_id = ?
              AND i.force_name = ?
            ORDER BY i.id
            """,
            (assessment_id, force_name)
        ).fetchall()
    else:
        rows = database.execute(
            """
            SELECT
                i.*,
                e.title AS evidence_title
            FROM five_forces_indicators i
            LEFT JOIN evidence e ON e.id = i.evidence_id
            WHERE i.assessment_id = ?
            ORDER BY i.force_name, i.id
            """,
            (assessment_id,)
        ).fetchall()

    return [dict(row) for row in rows]


def update_five_forces_indicator(
    indicator_id,
    acting_user_id,
    updates
):
    indicator_id = _positive_id(
        indicator_id,
        "Indicator ID"
    )

    if not isinstance(updates, dict) or not updates:
        raise FiveForcesValidationError(
            "Provide at least one indicator field to update."
        )

    allowed_fields = {
        "force_name",
        "indicator_name",
        "score",
        "weight",
        "explanation",
        "evidence_id"
    }

    if not set(updates).issubset(allowed_fields):
        raise FiveForcesValidationError(
            "One or more indicator fields cannot be updated."
        )

    database = get_db()
    acting_user_id = _validate_actor(
        database,
        acting_user_id
    )

    indicator = _get_indicator_or_raise(
        database,
        indicator_id
    )

    values = {}

    if "force_name" in updates:
        values["force_name"] = _validate_force(
            updates["force_name"]
        )

    if "indicator_name" in updates:
        values["indicator_name"] = _required_text(
            updates["indicator_name"],
            "Indicator name",
            MAX_INDICATOR_NAME_LENGTH
        )

    if "score" in updates:
        values["score"] = _validate_score(
            updates["score"]
        )

    if "weight" in updates:
        values["weight"] = _validate_weight(
            updates["weight"]
        )

    if "explanation" in updates:
        values["explanation"] = _optional_text(
            updates["explanation"],
            "Explanation",
            MAX_EXPLANATION_LENGTH
        )

    if "evidence_id" in updates:
        values["evidence_id"] = _validate_evidence(
            database,
            updates["evidence_id"]
        )

    assignments = ", ".join(
        f"{field} = ?" for field in values
    )

    try:
        database.execute("BEGIN IMMEDIATE")

        database.execute(
            f"""
            UPDATE five_forces_indicators
            SET {assignments}
            WHERE id = ?
            """,
            (*values.values(), indicator_id)
        )

        score_summary = _calculate_scores(
            database,
            indicator["assessment_id"]
        )

        _audit(
            acting_user_id,
            "FIVE_FORCES_INDICATOR_UPDATED",
            "Five Forces Indicator",
            indicator_id,
            f"Updated Five Forces indicator ID {indicator_id}."
        )

        database.commit()

        result = get_five_forces_indicator(indicator_id)
        result["score_summary"] = score_summary

        return result

    except Exception:
        database.rollback()
        raise


def delete_five_forces_indicator(
    indicator_id,
    acting_user_id
):
    indicator_id = _positive_id(
        indicator_id,
        "Indicator ID"
    )

    database = get_db()
    acting_user_id = _validate_actor(
        database,
        acting_user_id
    )

    indicator = _get_indicator_or_raise(
        database,
        indicator_id
    )

    try:
        database.execute("BEGIN IMMEDIATE")

        database.execute(
            """
            DELETE FROM strategic_analysis_evidence
            WHERE analysis_type = 'FIVE_FORCES'
              AND analysis_record_id = ?
            """,
            (indicator_id,)
        )

        database.execute(
            """
            DELETE FROM five_forces_indicators
            WHERE id = ?
            """,
            (indicator_id,)
        )

        score_summary = _calculate_scores(
            database,
            indicator["assessment_id"]
        )

        _audit(
            acting_user_id,
            "FIVE_FORCES_INDICATOR_DELETED",
            "Five Forces Indicator",
            indicator_id,
            (
                f"Deleted indicator "
                f"'{indicator['indicator_name']}' "
                f"from {indicator['force_name']}."
            )
        )

        database.commit()

        return {
            "deleted": True,
            "assessment_id": indicator["assessment_id"],
            "score_summary": score_summary
        }

    except Exception:
        database.rollback()
        raise
