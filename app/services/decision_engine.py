
# =========================================================
# STRATEGYSIM - STRATEGIC DECISION ENGINE
# =========================================================

from app.database.connection import get_db, execute_transaction
from app.services.audit_service import record_audit_log


# =========================================================
# EXCEPTIONS
# =========================================================

class DecisionError(Exception):
    """Base exception for strategic decision operations."""


class DecisionNotFoundError(DecisionError):
    """Raised when a decision record does not exist."""


class DecisionValidationError(DecisionError):
    """Raised when decision input is invalid."""


# =========================================================
# VALIDATION HELPERS
# =========================================================

def _positive_id(value, field_name):
    try:
        value = int(value)
    except (TypeError, ValueError):
        raise DecisionValidationError(
            f"{field_name} must be a valid ID."
        )

    if value <= 0:
        raise DecisionValidationError(
            f"{field_name} must be greater than zero."
        )

    return value


def _required_text(value, field_name, max_length=200):
    if not isinstance(value, str) or not value.strip():
        raise DecisionValidationError(
            f"{field_name} is required."
        )

    value = value.strip()

    if len(value) > max_length:
        raise DecisionValidationError(
            f"{field_name} cannot exceed {max_length} characters."
        )

    return value


def _optional_text(value, max_length=2000):
    if value is None:
        return None

    value = str(value).strip()

    if len(value) > max_length:
        raise DecisionValidationError(
            f"Text cannot exceed {max_length} characters."
        )

    return value or None


def _positive_weight(value):
    try:
        value = float(value)
    except (TypeError, ValueError):
        raise DecisionValidationError(
            "Criterion weight must be numeric."
        )

    if value < 0:
        raise DecisionValidationError(
            "Criterion weight cannot be negative."
        )

    return value


def _score_value(value):
    try:
        value = float(value)
    except (TypeError, ValueError):
        raise DecisionValidationError(
            "Score must be numeric."
        )

    if not 1 <= value <= 5:
        raise DecisionValidationError(
            "Score must be between 1 and 5."
        )

    return value


# =========================================================
# CREATE DECISION MATRIX
# =========================================================

def create_decision_matrix(
    company_id,
    matrix_name,
    objective,
    description,
    created_by
):
    company_id = _positive_id(company_id, "Company ID")
    matrix_name = _required_text(matrix_name, "Decision name")
    objective = _optional_text(objective)
    description = _optional_text(description)
    created_by = _positive_id(created_by, "User ID")

    def operation(database):
        company = database.execute(
            """
            SELECT id, name, company_type
            FROM companies
            WHERE id = ?
            """,
            (company_id,)
        ).fetchone()

        if not company:
            raise DecisionValidationError(
                "Selected company does not exist."
            )

        if company["company_type"] != "Target":
            raise DecisionValidationError(
                "Strategic decisions must be created for the target company."
            )

        user = database.execute(
            """
            SELECT id
            FROM users
            WHERE id = ? AND is_active = 1
            """,
            (created_by,)
        ).fetchone()

        if not user:
            raise DecisionValidationError(
                "Active user not found."
            )

        cursor = database.execute(
            """
            INSERT INTO decision_matrices (
                company_id,
                matrix_name,
                objective,
                description,
                created_by
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                company_id,
                matrix_name,
                objective,
                description,
                created_by
            )
        )

        matrix_id = cursor.lastrowid

        record_audit_log(
            created_by,
            "CREATE",
            "decision_matrix",
            matrix_id,
            f"Created strategic decision: {matrix_name}",
            commit=False
        )

        return matrix_id

    return execute_transaction(operation)


# =========================================================
# ADD DECISION ALTERNATIVE
# =========================================================

def add_decision_option(
    matrix_id,
    option_name,
    description,
    created_by
):
    matrix_id = _positive_id(matrix_id, "Matrix ID")
    option_name = _required_text(option_name, "Alternative name")
    description = _optional_text(description)
    created_by = _positive_id(created_by, "User ID")

    def operation(database):
        matrix = database.execute(
            """
            SELECT id
            FROM decision_matrices
            WHERE id = ?
            """,
            (matrix_id,)
        ).fetchone()

        if not matrix:
            raise DecisionNotFoundError(
                "Decision matrix not found."
            )

        cursor = database.execute(
            """
            INSERT INTO decision_options (
                matrix_id,
                option_name,
                description
            )
            VALUES (?, ?, ?)
            """,
            (matrix_id, option_name, description)
        )

        option_id = cursor.lastrowid

        record_audit_log(
            created_by,
            "CREATE",
            "decision_option",
            option_id,
            f"Added alternative: {option_name}",
            commit=False
        )

        return option_id

    return execute_transaction(operation)


# =========================================================
# ADD EVALUATION CRITERION
# =========================================================

def add_decision_criterion(
    matrix_id,
    criterion_name,
    weight,
    description,
    created_by
):
    matrix_id = _positive_id(matrix_id, "Matrix ID")
    criterion_name = _required_text(
        criterion_name,
        "Criterion name"
    )
    weight = _positive_weight(weight)
    description = _optional_text(description)
    created_by = _positive_id(created_by, "User ID")

    def operation(database):
        matrix = database.execute(
            """
            SELECT id
            FROM decision_matrices
            WHERE id = ?
            """,
            (matrix_id,)
        ).fetchone()

        if not matrix:
            raise DecisionNotFoundError(
                "Decision matrix not found."
            )

        cursor = database.execute(
            """
            INSERT INTO decision_criteria (
                matrix_id,
                criterion_name,
                weight,
                description
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                matrix_id,
                criterion_name,
                weight,
                description
            )
        )

        criterion_id = cursor.lastrowid

        record_audit_log(
            created_by,
            "CREATE",
            "decision_criterion",
            criterion_id,
            f"Added evaluation criterion: {criterion_name}",
            commit=False
        )

        return criterion_id

    return execute_transaction(operation)


# =========================================================
# SAVE OR UPDATE ALTERNATIVE SCORE
# =========================================================

def save_decision_score(
    matrix_id,
    option_id,
    criterion_id,
    score,
    justification,
    updated_by
):
    matrix_id = _positive_id(matrix_id, "Matrix ID")
    option_id = _positive_id(option_id, "Option ID")
    criterion_id = _positive_id(criterion_id, "Criterion ID")
    score = _score_value(score)
    justification = _optional_text(justification)
    updated_by = _positive_id(updated_by, "User ID")

    def operation(database):
        option = database.execute(
            """
            SELECT id, matrix_id, option_name
            FROM decision_options
            WHERE id = ? AND matrix_id = ?
            """,
            (option_id, matrix_id)
        ).fetchone()

        criterion = database.execute(
            """
            SELECT id, matrix_id, criterion_name, weight
            FROM decision_criteria
            WHERE id = ? AND matrix_id = ?
            """,
            (criterion_id, matrix_id)
        ).fetchone()

        if not option or not criterion:
            raise DecisionValidationError(
                "The selected alternative and criterion must "
                "belong to the same decision matrix."
            )

        weighted_score = score * float(criterion["weight"])

        database.execute(
            """
            INSERT INTO decision_scores (
                option_id,
                criterion_id,
                score,
                weighted_score,
                justification
            )
            VALUES (?, ?, ?, ?, ?)

            ON CONFLICT(option_id, criterion_id)
            DO UPDATE SET
                score = excluded.score,
                weighted_score = excluded.weighted_score,
                justification = excluded.justification
            """,
            (
                option_id,
                criterion_id,
                score,
                weighted_score,
                justification
            )
        )

        record_audit_log(
            updated_by,
            "UPDATE",
            "decision_score",
            option_id,
            (
                f"Recorded score {score} for "
                f"{option['option_name']} against "
                f"{criterion['criterion_name']}."
            ),
            commit=False
        )

        return True

    return execute_transaction(operation)


# =========================================================
# GET DECISION MATRIX
# =========================================================

def get_decision_matrix(matrix_id):
    matrix_id = _positive_id(matrix_id, "Matrix ID")
    database = get_db()

    matrix = database.execute(
        """
        SELECT
            dm.*,
            c.name AS company_name,
            u.full_name AS creator_name
        FROM decision_matrices dm
        JOIN companies c ON c.id = dm.company_id
        LEFT JOIN users u ON u.id = dm.created_by
        WHERE dm.id = ?
        """,
        (matrix_id,)
    ).fetchone()

    if not matrix:
        raise DecisionNotFoundError(
            "Decision matrix not found."
        )

    return dict(matrix)


# =========================================================
# LIST DECISION MATRICES
# =========================================================

def get_decision_matrices(company_id=None):
    database = get_db()

    query = """
        SELECT
            dm.*,
            c.name AS company_name,
            COUNT(DISTINCT do.id) AS option_count,
            COUNT(DISTINCT dc.id) AS criterion_count,
            u.full_name AS creator_name
        FROM decision_matrices dm
        JOIN companies c ON c.id = dm.company_id
        LEFT JOIN decision_options do ON do.matrix_id = dm.id
        LEFT JOIN decision_criteria dc ON dc.matrix_id = dm.id
        LEFT JOIN users u ON u.id = dm.created_by
    """

    params = []

    if company_id is not None:
        company_id = _positive_id(company_id, "Company ID")
        query += " WHERE dm.company_id = ?"
        params.append(company_id)

    query += """
        GROUP BY dm.id
        ORDER BY dm.created_at DESC, dm.id DESC
    """

    rows = database.execute(query, params).fetchall()

    return [dict(row) for row in rows]


# =========================================================
# GET OPTIONS AND CRITERIA
# =========================================================

def get_decision_options(matrix_id):
    matrix_id = _positive_id(matrix_id, "Matrix ID")
    database = get_db()

    rows = database.execute(
        """
        SELECT *
        FROM decision_options
        WHERE matrix_id = ?
        ORDER BY id
        """,
        (matrix_id,)
    ).fetchall()

    return [dict(row) for row in rows]


def get_decision_criteria(matrix_id):
    matrix_id = _positive_id(matrix_id, "Matrix ID")
    database = get_db()

    rows = database.execute(
        """
        SELECT *
        FROM decision_criteria
        WHERE matrix_id = ?
        ORDER BY id
        """,
        (matrix_id,)
    ).fetchall()

    return [dict(row) for row in rows]


# =========================================================
# GET SCORES
# =========================================================

def get_decision_scores(matrix_id):
    matrix_id = _positive_id(matrix_id, "Matrix ID")
    database = get_db()

    rows = database.execute(
        """
        SELECT
            ds.*,
            do.option_name,
            dc.criterion_name,
            dc.weight
        FROM decision_scores ds
        JOIN decision_options do
            ON do.id = ds.option_id
        JOIN decision_criteria dc
            ON dc.id = ds.criterion_id
        WHERE do.matrix_id = ?
          AND dc.matrix_id = ?
        ORDER BY do.id, dc.id
        """,
        (matrix_id, matrix_id)
    ).fetchall()

    return [dict(row) for row in rows]


# =========================================================
# WEIGHTED DECISION RANKING
# =========================================================

def calculate_decision_rankings(matrix_id):
    matrix_id = _positive_id(matrix_id, "Matrix ID")
    database = get_db()

    matrix = database.execute(
        """
        SELECT id
        FROM decision_matrices
        WHERE id = ?
        """,
        (matrix_id,)
    ).fetchone()

    if not matrix:
        raise DecisionNotFoundError(
            "Decision matrix not found."
        )

    criteria = get_decision_criteria(matrix_id)
    options = get_decision_options(matrix_id)

    if not options:
        raise DecisionValidationError(
            "Add at least one alternative before calculating rankings."
        )

    if not criteria:
        raise DecisionValidationError(
            "Add at least one evaluation criterion before ranking."
        )

    total_weight = sum(
        float(criterion["weight"])
        for criterion in criteria
    )

    if total_weight <= 0:
        raise DecisionValidationError(
            "The total criterion weight must be greater than zero."
        )

    results = []

    for option in options:
        scores = database.execute(
            """
            SELECT
                ds.score,
                ds.weighted_score,
                ds.justification,
                dc.weight,
                dc.criterion_name
            FROM decision_scores ds
            JOIN decision_criteria dc
                ON dc.id = ds.criterion_id
            WHERE ds.option_id = ?
              AND dc.matrix_id = ?
            """,
            (option["id"], matrix_id)
        ).fetchall()

        score_by_criterion = {
            row["criterion_name"]: row
            for row in scores
        }

        completed_count = len(scores)

        if completed_count != len(criteria):
            results.append({
                "option_id": option["id"],
                "option_name": option["option_name"],
                "description": option["description"],
                "weighted_score": None,
                "completion_count": completed_count,
                "total_criteria": len(criteria),
                "status": "Pending Evaluation",
                "rank": None,
                "criterion_scores": score_by_criterion,
            })
            continue

        weighted_total = sum(
            float(row["score"]) * float(row["weight"])
            for row in scores
        )

        final_score = weighted_total / total_weight

        results.append({
            "option_id": option["id"],
            "option_name": option["option_name"],
            "description": option["description"],
            "weighted_score": round(final_score, 3),
            "completion_count": completed_count,
            "total_criteria": len(criteria),
            "status": "Completed",
            "rank": None,
            "criterion_scores": score_by_criterion,
        })

    completed = [
        item for item in results
        if item["status"] == "Completed"
    ]

    completed.sort(
        key=lambda item: item["weighted_score"],
        reverse=True
    )

    previous_score = None
    current_rank = 0

    for index, item in enumerate(completed, start=1):
        if item["weighted_score"] != previous_score:
            current_rank = index

        item["rank"] = current_rank
        previous_score = item["weighted_score"]

    return completed + [
        item for item in results
        if item["status"] == "Pending Evaluation"
    ]
