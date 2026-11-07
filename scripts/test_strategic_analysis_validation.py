"""
StrategySim - Strategic Analysis Validation Tests.

Run:
    python -m scripts.test_strategic_analysis_validation
"""

from app.strategic_analysis.validation import (
    StrategicAnalysisValidationError,
    validate_positive_id,
    validate_required_text,
    validate_optional_text,
    validate_score,
    validate_positive_number,
    validate_choice,
    validate_iso_date,
    validate_assessment_name,
    validate_factor_name,
    validate_description,
    validate_summary,
    ALLOWED_SWOT_FACTOR_TYPES,
    ALLOWED_PESTLE_CATEGORIES,
)


passed = 0
failed = 0


def check(test_name, callback, expected=None, should_raise=False):
    global passed, failed

    try:
        result = callback()

        if should_raise:
            raise AssertionError(
                "Expected StrategicAnalysisValidationError, "
                "but no exception was raised."
            )

        if result != expected:
            raise AssertionError(
                f"Expected {expected!r}, got {result!r}"
            )

        passed += 1
        print(f"[PASS] {test_name}")

    except StrategicAnalysisValidationError:
        if should_raise:
            passed += 1
            print(f"[PASS] {test_name}")
        else:
            failed += 1
            print(f"[FAIL] {test_name}: Unexpected validation error")

    except Exception as error:
        failed += 1
        print(f"[FAIL] {test_name}: {error}")


def run_tests():

    print("\n==========================================")
    print(" STRATEGIC ANALYSIS VALIDATION TESTS")
    print("==========================================\n")

    # -----------------------------------------
    # Positive ID tests
    # -----------------------------------------

    check(
        "Positive integer ID",
        lambda: validate_positive_id(10),
        10,
    )

    check(
        "Numeric string ID",
        lambda: validate_positive_id("25"),
        25,
    )

    check(
        "Reject zero ID",
        lambda: validate_positive_id(0),
        should_raise=True,
    )

    check(
        "Reject negative ID",
        lambda: validate_positive_id(-5),
        should_raise=True,
    )

    check(
        "Reject boolean ID",
        lambda: validate_positive_id(True),
        should_raise=True,
    )

    # -----------------------------------------
    # Required text tests
    # -----------------------------------------

    check(
        "Required text normalization",
        lambda: validate_required_text("  Strategy  "),
        "Strategy",
    )

    check(
        "Reject empty required text",
        lambda: validate_required_text("   "),
        should_raise=True,
    )

    check(
        "Reject non-string required text",
        lambda: validate_required_text(123),
        should_raise=True,
    )

    # -----------------------------------------
    # Optional text tests
    # -----------------------------------------

    check(
        "Optional text accepts None",
        lambda: validate_optional_text(None),
        None,
    )

    check(
        "Optional text converts whitespace to None",
        lambda: validate_optional_text("   "),
        None,
    )

    check(
        "Optional text normalization",
        lambda: validate_optional_text("  Notes  "),
        "Notes",
    )

    # -----------------------------------------
    # Score tests
    # -----------------------------------------

    check(
        "Minimum score",
        lambda: validate_score(1),
        1,
    )

    check(
        "Maximum score",
        lambda: validate_score(5),
        5,
    )

    check(
        "Numeric string score",
        lambda: validate_score("3"),
        3,
    )

    check(
        "Reject score below range",
        lambda: validate_score(0),
        should_raise=True,
    )

    check(
        "Reject score above range",
        lambda: validate_score(6),
        should_raise=True,
    )

    check(
        "Reject decimal score",
        lambda: validate_score(3.5),
        should_raise=True,
    )

    check(
        "Reject boolean score",
        lambda: validate_score(True),
        should_raise=True,
    )

    check(
        "Optional score accepts None",
        lambda: validate_score(None, allow_none=True),
        None,
    )

    # -----------------------------------------
    # Positive numeric tests
    # -----------------------------------------

    check(
        "Positive integer weight",
        lambda: validate_positive_number(2),
        2.0,
    )

    check(
        "Positive decimal weight",
        lambda: validate_positive_number("1.5"),
        1.5,
    )

    check(
        "Reject zero weight",
        lambda: validate_positive_number(0),
        should_raise=True,
    )

    check(
        "Reject negative weight",
        lambda: validate_positive_number(-2),
        should_raise=True,
    )

    check(
        "Reject infinite weight",
        lambda: validate_positive_number(float("inf")),
        should_raise=True,
    )

    check(
        "Reject boolean weight",
        lambda: validate_positive_number(True),
        should_raise=True,
    )

    # -----------------------------------------
    # Allowed choice tests
    # -----------------------------------------

    check(
        "Valid SWOT factor type",
        lambda: validate_choice(
            "Strength",
            ALLOWED_SWOT_FACTOR_TYPES,
        ),
        "Strength",
    )

    check(
        "Valid PESTLE category",
        lambda: validate_choice(
            "Technological",
            ALLOWED_PESTLE_CATEGORIES,
        ),
        "Technological",
    )

    check(
        "Case-insensitive category",
        lambda: validate_choice(
            "political",
            ALLOWED_PESTLE_CATEGORIES,
            case_sensitive=False,
        ),
        "Political",
    )

    check(
        "Reject invalid SWOT factor type",
        lambda: validate_choice(
            "Advantage",
            ALLOWED_SWOT_FACTOR_TYPES,
        ),
        should_raise=True,
    )

    # -----------------------------------------
    # Date tests
    # -----------------------------------------

    check(
        "Valid ISO date",
        lambda: validate_iso_date("2026-11-07"),
        "2026-11-07",
    )

    check(
        "Reject invalid calendar date",
        lambda: validate_iso_date("2026-02-30"),
        should_raise=True,
    )

    check(
        "Reject incorrect date format",
        lambda: validate_iso_date("07-11-2026"),
        should_raise=True,
    )

    check(
        "Optional date accepts None",
        lambda: validate_iso_date(None, allow_none=True),
        None,
    )

    # -----------------------------------------
    # Domain-specific validators
    # -----------------------------------------

    check(
        "Assessment name",
        lambda: validate_assessment_name(
            "  Annual SWOT Assessment  "
        ),
        "Annual SWOT Assessment",
    )

    check(
        "Reject short assessment name",
        lambda: validate_assessment_name("A"),
        should_raise=True,
    )

    check(
        "Factor name",
        lambda: validate_factor_name(
            "Battery Technology"
        ),
        "Battery Technology",
    )

    check(
        "Optional description",
        lambda: validate_description(None),
        None,
    )

    check(
        "Required description",
        lambda: validate_description(
            "High battery manufacturing cost.",
            allow_none=False,
        ),
        "High battery manufacturing cost.",
    )

    check(
        "Optional summary",
        lambda: validate_summary(None),
        None,
    )

    check(
        "Assessment summary",
        lambda: validate_summary(
            "The company has strong market potential."
        ),
        "The company has strong market potential.",
    )

    # -----------------------------------------
    # Final result
    # -----------------------------------------

    print("\n==========================================")
    print(" TEST RESULTS")
    print("==========================================")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print(f"Total:  {passed + failed}")
    print("==========================================")

    if failed:
        raise SystemExit(1)

    print("\nAll validation tests passed successfully.")


if __name__ == "__main__":
    run_tests()