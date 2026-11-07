"""
StrategySim - Strategic Analysis Validation Utilities.

Provides shared input validation for all Strategic Analysis modules.

Supported modules:
    - SWOT
    - PESTLE
    - Five Forces
    - Value Chain
    - Strategic Evidence

This module contains no database operations and does not modify
application state.
"""

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
import math
import re


# =========================================================
# CUSTOM EXCEPTION
# =========================================================

class StrategicAnalysisValidationError(ValueError):
    """
    Raised when Strategic Analysis input validation fails.
    """

    pass


# =========================================================
# VALIDATION LIMITS
# =========================================================

ASSESSMENT_NAME_MAX_LENGTH = 150
FACTOR_NAME_MAX_LENGTH = 200
DESCRIPTION_MAX_LENGTH = 2000
SUMMARY_MAX_LENGTH = 5000
RESPONSE_STRATEGY_MAX_LENGTH = 2000
SOURCE_NAME_MAX_LENGTH = 200
URL_MAX_LENGTH = 2048

MIN_SCORE = 1
MAX_SCORE = 5

ALLOWED_ANALYSIS_TYPES = {
    "SWOT",
    "PESTLE",
    "FIVE_FORCES",
    "VALUE_CHAIN",
}

ALLOWED_SWOT_FACTOR_TYPES = {
    "Strength",
    "Weakness",
    "Opportunity",
    "Threat",
}

ALLOWED_PESTLE_CATEGORIES = {
    "Political",
    "Economic",
    "Social",
    "Technological",
    "Legal",
    "Environmental",
}

ALLOWED_FIVE_FORCES = {
    "Buyer Power",
    "Supplier Power",
    "Competitive Rivalry",
    "Threat of Substitution",
    "Threat of New Entrants",
}

ALLOWED_VALUE_CHAIN_CATEGORIES = {
    "Primary",
    "Support",
}


# =========================================================
# INTERNAL HELPERS
# =========================================================

def _field_name(field):
    """
    Normalize a field label for error messages.
    """

    if not isinstance(field, str) or not field.strip():
        return "Value"

    return field.strip()


def _raise_validation_error(field, message):
    """
    Raise a consistent validation exception.
    """

    raise StrategicAnalysisValidationError(
        f"{_field_name(field)}: {message}"
    )


def _is_boolean(value):
    """
    Return True for boolean values.

    Python treats bool as a subclass of int, so booleans
    must be rejected explicitly in numeric validators.
    """

    return isinstance(value, bool)


# =========================================================
# IDENTIFIER VALIDATION
# =========================================================

def validate_positive_id(value, field="ID"):
    """
    Validate a positive integer identifier.

    Accepts:
        1
        "1"

    Rejects:
        0
        -1
        True
        1.5
        "abc"
        None

    Returns:
        int
    """

    if _is_boolean(value):
        _raise_validation_error(
            field,
            "must be a positive integer."
        )

    if isinstance(value, int):
        parsed_value = value

    elif isinstance(value, str):
        normalized = value.strip()

        if not re.fullmatch(r"[0-9]+", normalized):
            _raise_validation_error(
                field,
                "must be a positive integer."
            )

        try:
            parsed_value = int(normalized)
        except ValueError:
            _raise_validation_error(
                field,
                "must be a valid integer."
            )

    else:
        _raise_validation_error(
            field,
            "must be a positive integer."
        )

    if parsed_value <= 0:
        _raise_validation_error(
            field,
            "must be greater than zero."
        )

    return parsed_value


# =========================================================
# REQUIRED TEXT VALIDATION
# =========================================================

def validate_required_text(
    value,
    field="Text",
    max_length=200,
    min_length=1,
):
    """
    Validate and normalize required text.

    Rules:
        - Must be a string.
        - Cannot be empty.
        - Leading and trailing whitespace is removed.
        - Must satisfy minimum and maximum length.

    Returns:
        str
    """

    if not isinstance(value, str):
        _raise_validation_error(
            field,
            "must be provided as text."
        )

    normalized = value.strip()

    if not normalized:
        _raise_validation_error(
            field,
            "cannot be empty."
        )

    if not isinstance(min_length, int) or min_length < 0:
        raise ValueError("min_length must be a non-negative integer.")

    if not isinstance(max_length, int) or max_length < 1:
        raise ValueError("max_length must be a positive integer.")

    if min_length > max_length:
        raise ValueError(
            "min_length cannot exceed max_length."
        )

    if len(normalized) < min_length:
        _raise_validation_error(
            field,
            f"must contain at least {min_length} characters."
        )

    if len(normalized) > max_length:
        _raise_validation_error(
            field,
            f"cannot exceed {max_length} characters."
        )

    return normalized


# =========================================================
# OPTIONAL TEXT VALIDATION
# =========================================================

def validate_optional_text(
    value,
    field="Text",
    max_length=2000,
):
    """
    Validate optional text.

    Rules:
        - None is accepted.
        - Empty or whitespace-only text becomes None.
        - Non-string values are rejected.
        - Maximum length is enforced.

    Returns:
        str or None
    """

    if value is None:
        return None

    if not isinstance(value, str):
        _raise_validation_error(
            field,
            "must be text or empty."
        )

    normalized = value.strip()

    if not normalized:
        return None

    if len(normalized) > max_length:
        _raise_validation_error(
            field,
            f"cannot exceed {max_length} characters."
        )

    return normalized


# =========================================================
# SCORE VALIDATION
# =========================================================

def validate_score(
    value,
    field="Score",
    minimum=MIN_SCORE,
    maximum=MAX_SCORE,
    allow_none=False,
):
    """
    Validate an integer score within a specified range.

    Default range:
        1 to 5

    Accepts:
        1
        3
        5
        "4"

    Rejects:
        True
        1.5
        0
        6
        "invalid"

    Returns:
        int or None
    """

    if value is None:
        if allow_none:
            return None

        _raise_validation_error(
            field,
            "is required."
        )

    if _is_boolean(value):
        _raise_validation_error(
            field,
            "must be an integer score."
        )

    if isinstance(value, int):
        parsed_value = value

    elif isinstance(value, str):
        normalized = value.strip()

        if not re.fullmatch(r"-?[0-9]+", normalized):
            _raise_validation_error(
                field,
                "must be an integer score."
            )

        try:
            parsed_value = int(normalized)
        except ValueError:
            _raise_validation_error(
                field,
                "must be a valid integer score."
            )

    else:
        _raise_validation_error(
            field,
            "must be an integer score."
        )

    if parsed_value < minimum or parsed_value > maximum:
        _raise_validation_error(
            field,
            f"must be between {minimum} and {maximum}."
        )

    return parsed_value


# =========================================================
# POSITIVE NUMBER VALIDATION
# =========================================================

def validate_positive_number(
    value,
    field="Number",
    allow_none=False,
):
    """
    Validate a finite positive numeric value.

    Accepts integers, floats and numeric strings.

    Rejects:
        - Boolean values
        - Zero
        - Negative values
        - NaN
        - Infinity
        - Non-numeric text

    Returns:
        float or None
    """

    if value is None:
        if allow_none:
            return None

        _raise_validation_error(
            field,
            "is required."
        )

    if _is_boolean(value):
        _raise_validation_error(
            field,
            "must be a positive number."
        )

    try:
        parsed_value = Decimal(str(value).strip())
    except (InvalidOperation, ValueError, TypeError):
        _raise_validation_error(
            field,
            "must be a valid number."
        )

    if not parsed_value.is_finite():
        _raise_validation_error(
            field,
            "must be a finite number."
        )

    if parsed_value <= 0:
        _raise_validation_error(
            field,
            "must be greater than zero."
        )

    result = float(parsed_value)

    if not math.isfinite(result):
        _raise_validation_error(
            field,
            "is outside the supported numeric range."
        )

    return result


# =========================================================
# ALLOWED VALUE VALIDATION
# =========================================================

def validate_choice(
    value,
    allowed_values,
    field="Selection",
    case_sensitive=True,
):
    """
    Validate that a value belongs to an allowed set.

    Parameters:
        value:
            User-provided value.

        allowed_values:
            Set, tuple or list of permitted values.

        field:
            Field name used in error messages.

        case_sensitive:
            Whether matching should be case-sensitive.

    Returns:
        Canonical allowed value.
    """

    if not isinstance(value, str):
        _raise_validation_error(
            field,
            "must be a valid selection."
        )

    if not isinstance(allowed_values, (set, tuple, list)):
        raise TypeError(
            "allowed_values must be a set, tuple or list."
        )

    normalized = value.strip()

    if not normalized:
        _raise_validation_error(
            field,
            "selection is required."
        )

    if case_sensitive:
        if normalized not in allowed_values:
            options = ", ".join(
                sorted(str(item) for item in allowed_values)
            )

            _raise_validation_error(
                field,
                f"must be one of: {options}."
            )

        return normalized

    lookup = {
        str(item).casefold(): item
        for item in allowed_values
    }

    matched_value = lookup.get(normalized.casefold())

    if matched_value is None:
        options = ", ".join(
            sorted(str(item) for item in allowed_values)
        )

        _raise_validation_error(
            field,
            f"must be one of: {options}."
        )

    return matched_value


# =========================================================
# ISO DATE VALIDATION
# =========================================================

def validate_iso_date(
    value,
    field="Date",
    allow_none=False,
):
    """
    Validate a date in ISO 8601 format.

    Expected format:
        YYYY-MM-DD

    Also accepts datetime.date objects.

    Returns:
        str in YYYY-MM-DD format, or None.
    """

    if value is None:
        if allow_none:
            return None

        _raise_validation_error(
            field,
            "is required."
        )

    if isinstance(value, datetime):
        return value.date().isoformat()

    if isinstance(value, date):
        return value.isoformat()

    if not isinstance(value, str):
        _raise_validation_error(
            field,
            "must be a valid ISO date (YYYY-MM-DD)."
        )

    normalized = value.strip()

    try:
        parsed_date = date.fromisoformat(normalized)
    except ValueError:
        _raise_validation_error(
            field,
            "must use the YYYY-MM-DD format and be a valid date."
        )

    if parsed_date.isoformat() != normalized:
        _raise_validation_error(
            field,
            "must use the YYYY-MM-DD format."
        )

    return parsed_date.isoformat()


# =========================================================
# DOMAIN-SPECIFIC TEXT VALIDATORS
# =========================================================

def validate_assessment_name(value):
    """
    Validate a strategic assessment name.
    """

    return validate_required_text(
        value,
        field="Assessment name",
        min_length=2,
        max_length=ASSESSMENT_NAME_MAX_LENGTH,
    )


def validate_factor_name(value):
    """
    Validate a SWOT, PESTLE or analytical factor name.
    """

    return validate_required_text(
        value,
        field="Factor name",
        min_length=2,
        max_length=FACTOR_NAME_MAX_LENGTH,
    )


def validate_description(value, allow_none=True):
    """
    Validate an analytical factor description.
    """

    if allow_none:
        return validate_optional_text(
            value,
            field="Description",
            max_length=DESCRIPTION_MAX_LENGTH,
        )

    return validate_required_text(
        value,
        field="Description",
        min_length=1,
        max_length=DESCRIPTION_MAX_LENGTH,
    )


def validate_summary(value, allow_none=True):
    """
    Validate an assessment summary.
    """

    if allow_none:
        return validate_optional_text(
            value,
            field="Summary",
            max_length=SUMMARY_MAX_LENGTH,
        )

    return validate_required_text(
        value,
        field="Summary",
        min_length=1,
        max_length=SUMMARY_MAX_LENGTH,
    )