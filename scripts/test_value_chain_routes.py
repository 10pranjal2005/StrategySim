import os
import shutil
import tempfile

from app import create_app, login_manager
from app.value_chain.services import (
    create_value_chain_assessment,
    create_value_chain_activity,
)


def main():
    original_db = os.path.join("instance", "strategysim.db")

    if not os.path.exists(original_db):
        print("[FAIL] Original database not found:", original_db)
        return

    temporary_directory = tempfile.TemporaryDirectory()
    temporary_db = os.path.join(
        temporary_directory.name,
        "strategysim_test.db"
    )

    shutil.copy2(original_db, temporary_db)

    app = create_app()

    login_manager.session_protection = None

    app.config.update(
        TESTING=True,
        DATABASE_PATH=temporary_db,
        WTF_CSRF_ENABLED=False,
    )

    results = []

    def record_test(description, passed, detail=""):
        results.append(passed)
        status = "PASS" if passed else "FAIL"

        print(f"[{status}] {description}")

        if detail:
            print("       ", detail)

    try:
        with app.app_context():

            assessment = create_value_chain_assessment(
                company_id=1,
                assessment_name="Route Testing - Value Chain",
                acting_user_id=1,
                summary="Temporary integration testing assessment."
            )

            assessment_id = (
                assessment["id"]
                if isinstance(assessment, dict)
                else assessment
            )

            activity = create_value_chain_activity(
                assessment_id=assessment_id,
                activity_category="Primary",
                activity_name="Route Testing Activity",
                acting_user_id=1,
                description="Temporary activity for route testing.",
                cost_contribution=10.0,
                strategic_importance=3,
                competitive_advantage="Temporary test description."
            )

            activity_id = (
                activity["id"]
                if isinstance(activity, dict)
                else activity
            )

            print("\nTemporary test records created.")
            print("Assessment ID:", assessment_id)
            print("Activity ID:", activity_id)

        urls = [
            ("Assessment Index", "/value-chain/", True),
            ("Create Assessment", "/value-chain/new", False),
            (
                "Assessment Detail",
                f"/value-chain/{assessment_id}",
                True
            ),
            (
                "Edit Assessment",
                f"/value-chain/{assessment_id}/edit",
                False
            ),
            (
                "Create Activity",
                f"/value-chain/{assessment_id}/activities/new",
                False
            ),
            (
                "Edit Activity",
                f"/value-chain/activities/{activity_id}/edit",
                False
            ),
        ]

        roles = [
            ("Administrator", 1),
            ("Analyst", 8),
            ("Viewer", 10),
        ]

        for role_name, user_id in roles:

            print(f"\n========== {role_name.upper()} GET TESTS ==========")

            client = app.test_client()

            with client.session_transaction() as session:
                session["_user_id"] = str(user_id)
                session["_fresh"] = True

            for page_name, url, read_only_page in urls:

                try:
                    response = client.get(url)

                    if role_name == "Viewer" and not read_only_page:
                        expected_status = 403
                    else:
                        expected_status = 200

                    record_test(
                        f"{role_name}: {page_name}",
                        response.status_code == expected_status,
                        (
                            f"Expected HTTP {expected_status}, "
                            f"received HTTP {response.status_code}"
                        )
                    )

                except Exception as error:
                    record_test(
                        f"{role_name}: {page_name}",
                        False,
                        str(error)
                    )

        print("\n========== ANONYMOUS GET TESTS ==========")

        anonymous_client = app.test_client()

        for page_name, url, _ in urls:

            try:
                response = anonymous_client.get(
                    url,
                    follow_redirects=False
                )

                record_test(
                    f"Anonymous blocked: {page_name}",
                    response.status_code in (301, 302, 303, 401),
                    f"HTTP {response.status_code}"
                )

            except Exception as error:
                record_test(
                    f"Anonymous blocked: {page_name}",
                    False,
                    str(error)
                )

        passed = sum(results)
        failed = len(results) - passed

        print("\n========================================")
        print("VALUE CHAIN ROUTE TEST SUMMARY")
        print("========================================")
        print("Total tests:", len(results))
        print("Passed:", passed)
        print("Failed:", failed)

        if failed == 0:
            print("\nALL VALUE CHAIN ROUTE GET TESTS PASSED.")
        else:
            print("\nSOME TESTS FAILED. REVIEW THE OUTPUT.")

    finally:
        temporary_directory.cleanup()


if __name__ == "__main__":
    main()