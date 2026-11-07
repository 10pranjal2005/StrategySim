
"""
StrategySim - Competitor Intelligence Route Tests

File:
    scripts/test_competitor_routes.py

Purpose:
    Test the Competitor Intelligence Flask routes using an
    isolated temporary SQLite database.

Important:
    This script does NOT use or modify:
        instance/strategysim.db

    It tests:
        - Authentication
        - Role-based access control
        - Competitor directory and profiles
        - Relationship creation
        - Relationship updates
        - Relationship deletion
        - Form validation
        - CSRF protection
        - Safe redirect handling
        - Audit logging
        - SQLite database integrity

Run from the project root:
    python scripts/test_competitor_routes.py
"""

import sqlite3
import tempfile
import unittest

from pathlib import Path
from unittest.mock import patch

from werkzeug.security import generate_password_hash

from flask_wtf.csrf import generate_csrf

from app import create_app, login_manager
from app.config import TestingConfig, configurations


# =========================================================
# TEST APPLICATION CONFIGURATION
# =========================================================

class CompetitorRouteTests(unittest.TestCase):
    """
    Automated tests for Competitor Intelligence routes.
    """

    def setUp(self):
        """
        Create a new temporary database and Flask application
        for each test.

        The original project database is never used.
        """

        self.temp_directory = tempfile.TemporaryDirectory()

        self.db_path = (
            Path(self.temp_directory.name)
            / "competitor_route_tests.db"
        )

        self.original_testing_config = configurations["testing"]

        TestConfig = type(
            "CompetitorRouteTestingConfig",
            (TestingConfig,),
            {
                "TESTING": True,
                "WTF_CSRF_ENABLED": True,
                "SECRET_KEY": "competitor-route-test-secret",
                "DATABASE_PATH": str(self.db_path),
                "SESSION_COOKIE_SECURE": False,
            },
        )

        configurations["testing"] = TestConfig

        try:
            self.app = create_app("testing")
        finally:
            configurations["testing"] = self.original_testing_config

        self.app.config.update(
            TESTING=True,
            WTF_CSRF_ENABLED=True,
            WTF_CSRF_CHECK_DEFAULT=True,
            PROPAGATE_EXCEPTIONS=True,
        )

        self.client = self.app.test_client()

        # Replace template rendering during route tests.
        # This allows route behavior to be tested independently
        # of the frontend templates.
        self.template_patch = patch(
            "app.competitors.routes.render_template",
            side_effect=self.fake_render_template,
        )

        self.template_patch.start()

        self.seed_test_data()

    def tearDown(self):
        """
        Stop patches and remove the temporary database.
        """

        self.template_patch.stop()

        self.temp_directory.cleanup()

    # =====================================================
    # TEMPLATE MOCK
    # =====================================================

    @staticmethod
    def fake_render_template(template_name, **context):
        """
        Return a CSRF token instead of rendering an HTML template.

        The token is generated during the actual Flask request
        so it is associated with the test client's session.
        """

        return generate_csrf()

    # =====================================================
    # DATABASE HELPERS
    # =====================================================

    def get_connection(self):
        """
        Open a direct SQLite connection to the temporary database.
        """

        connection = sqlite3.connect(str(self.db_path))

        connection.row_factory = sqlite3.Row

        connection.execute("PRAGMA foreign_keys = ON")

        return connection

    def seed_test_data(self):
        """
        Insert isolated test users, industry and companies.
        """

        connection = self.get_connection()

        try:
            cursor = connection.cursor()

            password_hash = generate_password_hash(
                "TestPassword123!"
            )

            test_users = [
                (
                    "Test Administrator",
                    "admin-test@strategysim.local",
                    password_hash,
                    "Administrator",
                ),
                (
                    "Test Analyst",
                    "analyst-test@strategysim.local",
                    password_hash,
                    "Analyst",
                ),
                (
                    "Test Viewer",
                    "viewer-test@strategysim.local",
                    password_hash,
                    "Viewer",
                ),
            ]

            cursor.executemany(
                """
                INSERT INTO users (
                    full_name,
                    email,
                    password_hash,
                    role
                )
                VALUES (?, ?, ?, ?)
                """,
                test_users,
            )

            cursor.execute(
                """
                SELECT id, role
                FROM users
                """
            )

            user_rows = cursor.fetchall()

            self.user_ids = {
                row["role"]: row["id"]
                for row in user_rows
            }

            cursor.execute(
                """
                INSERT INTO industries (
                    name,
                    sector,
                    description,
                    geography,
                    industry_type
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    "Illustrative Indian Electric Two-Wheeler Industry",
                    "Automotive",
                    "Illustrative test industry. Not factual market data.",
                    "India",
                    "Electric Two-Wheeler",
                ),
            )

            self.industry_id = cursor.lastrowid

            admin_id = self.user_ids["Administrator"]

            cursor.execute(
                """
                INSERT INTO companies (
                    industry_id,
                    name,
                    company_type,
                    description,
                    headquarters,
                    is_demo,
                    created_by
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    self.industry_id,
                    "Illustrative VoltEdge Motors",
                    "Target",
                    "Illustrative target company for route testing.",
                    "India",
                    1,
                    admin_id,
                ),
            )

            self.target_company_id = cursor.lastrowid

            cursor.execute(
                """
                INSERT INTO companies (
                    industry_id,
                    name,
                    company_type,
                    description,
                    headquarters,
                    is_demo,
                    created_by
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    self.industry_id,
                    "Illustrative Competitor One",
                    "Competitor",
                    "Illustrative competitor for route testing.",
                    "India",
                    1,
                    admin_id,
                ),
            )

            self.competitor_id = cursor.lastrowid

            cursor.execute(
                """
                INSERT INTO companies (
                    industry_id,
                    name,
                    company_type,
                    description,
                    headquarters,
                    is_demo,
                    created_by
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    self.industry_id,
                    "Illustrative Other Company",
                    "Other",
                    "Illustrative company used for validation testing.",
                    "India",
                    1,
                    admin_id,
                ),
            )

            self.other_company_id = cursor.lastrowid

            connection.commit()

        finally:
            connection.close()

    # =====================================================
    # AUTHENTICATION HELPERS
    # =====================================================

    def login_as(self, role):
        """
        Authenticate the test client as a selected test user.

        The Flask-Login session is initialized with the session
        identifier required by strong session protection.
        """

        user_id = self.user_ids[role]

        with self.client.session_transaction() as session:
            session["_user_id"] = str(user_id)
            session["_fresh"] = True
            session["_id"] = (
                login_manager._session_identifier_generator()
            )

    def get_csrf_token(self):
        """
        Retrieve a CSRF token through an authenticated GET request.
        """

        response = self.client.get("/competitors/")

        self.assertEqual(
            response.status_code,
            200,
            "Could not retrieve a CSRF token.",
        )

        token = response.get_data(as_text=True).strip()

        self.assertTrue(
            token,
            "The generated CSRF token is empty.",
        )

        return token

    def csrf_headers(self, token):
        """
        Build the request headers required by Flask-WTF.
        """

        return {
            "X-CSRFToken": token,
        }

    def create_relationship(self, role="Analyst"):
        """
        Create a relationship through the actual Flask route.
        """

        self.login_as(role)

        token = self.get_csrf_token()

        response = self.client.post(
            (
                "/competitors/relationships/create/"
                f"{self.target_company_id}"
            ),
            data={
                "competitor_id": str(self.competitor_id),
                "competitive_strength": "3",
                "notes": "Initial illustrative test relationship.",
                "csrf_token": token,
            },
            headers=self.csrf_headers(token),
            follow_redirects=False,
        )

        return response

    def get_relationship_id(self):
        """
        Retrieve the relationship ID from the temporary database.
        """

        connection = self.get_connection()

        try:
            row = connection.execute(
                """
                SELECT id
                FROM competitor_relationships
                WHERE company_id = ?
                  AND competitor_id = ?
                """,
                (
                    self.target_company_id,
                    self.competitor_id,
                ),
            ).fetchone()

            return row["id"] if row else None

        finally:
            connection.close()

    def get_audit_actions(self):
        """
        Retrieve audit actions for the test users.
        """

        connection = self.get_connection()

        try:
            rows = connection.execute(
                """
                SELECT action, entity_type, entity_id
                FROM audit_logs
                ORDER BY id
                """
            ).fetchall()

            return [dict(row) for row in rows]

        finally:
            connection.close()

    # =====================================================
    # 1. AUTHENTICATION TESTS
    # =====================================================

    def test_01_anonymous_user_redirected_from_directory(self):
        response = self.client.get("/competitors/")

        self.assertEqual(response.status_code, 302)

        self.assertIn(
            "/auth/login",
            response.headers.get("Location", ""),
        )

    def test_02_anonymous_user_redirected_from_competitor_profile(self):
        response = self.client.get(
            f"/competitors/{self.competitor_id}"
        )

        self.assertEqual(response.status_code, 302)

        self.assertIn(
            "/auth/login",
            response.headers.get("Location", ""),
        )

    def test_03_authenticated_viewer_can_access_directory(self):
        self.login_as("Viewer")

        response = self.client.get("/competitors/")

        self.assertEqual(response.status_code, 200)

    # =====================================================
    # 2. ROLE-BASED ACCESS CONTROL TESTS
    # =====================================================

    def test_04_viewer_cannot_create_relationship(self):
        self.login_as("Viewer")

        token = self.get_csrf_token()

        response = self.client.post(
            (
                "/competitors/relationships/create/"
                f"{self.target_company_id}"
            ),
            data={
                "competitor_id": str(self.competitor_id),
                "competitive_strength": "3",
                "notes": "Viewer permission test.",
                "csrf_token": token,
            },
            headers=self.csrf_headers(token),
        )

        self.assertEqual(response.status_code, 403)

        self.assertIsNone(self.get_relationship_id())

    def test_05_analyst_can_create_relationship(self):
        response = self.create_relationship("Analyst")

        self.assertEqual(response.status_code, 302)

        self.assertIsNotNone(self.get_relationship_id())

    def test_06_administrator_can_create_relationship(self):
        response = self.create_relationship("Administrator")

        self.assertEqual(response.status_code, 302)

        self.assertIsNotNone(self.get_relationship_id())

    # =====================================================
    # 3. DIRECTORY AND PROFILE TESTS
    # =====================================================

    def test_07_competitor_directory_loads(self):
        self.login_as("Analyst")

        response = self.client.get("/competitors/")

        self.assertEqual(response.status_code, 200)

    def test_08_competitor_directory_search_loads(self):
        self.login_as("Analyst")

        response = self.client.get(
            "/competitors/?search=Competitor"
        )

        self.assertEqual(response.status_code, 200)

    def test_09_competitor_directory_industry_filter_loads(self):
        self.login_as("Analyst")

        response = self.client.get(
            (
                "/competitors/?industry_id="
                f"{self.industry_id}"
            )
        )

        self.assertEqual(response.status_code, 200)

    def test_10_competitor_profile_loads(self):
        self.login_as("Analyst")

        response = self.client.get(
            f"/competitors/{self.competitor_id}"
        )

        self.assertEqual(response.status_code, 200)

    def test_11_nonexistent_competitor_profile_returns_404(self):
        self.login_as("Analyst")

        response = self.client.get(
            "/competitors/999999"
        )

        self.assertEqual(response.status_code, 404)

    # =====================================================
    # 4. RELATIONSHIP DIRECTORY TESTS
    # =====================================================

    def test_12_target_company_relationship_page_loads(self):
        self.login_as("Analyst")

        response = self.client.get(
            (
                "/competitors/for-company/"
                f"{self.target_company_id}"
            )
        )

        self.assertEqual(response.status_code, 200)

    def test_13_nonexistent_target_company_returns_404(self):
        self.login_as("Analyst")

        response = self.client.get(
            "/competitors/for-company/999999"
        )

        self.assertEqual(response.status_code, 404)

    # =====================================================
    # 5. RELATIONSHIP CREATION TESTS
    # =====================================================

    def test_14_relationship_creation_succeeds(self):
        response = self.create_relationship("Analyst")

        self.assertEqual(response.status_code, 302)

        self.assertIsNotNone(self.get_relationship_id())

    def test_15_duplicate_relationship_is_rejected(self):
        first_response = self.create_relationship("Analyst")

        self.assertEqual(first_response.status_code, 302)

        second_token = self.get_csrf_token()

        second_response = self.client.post(
            (
                "/competitors/relationships/create/"
                f"{self.target_company_id}"
            ),
            data={
                "competitor_id": str(self.competitor_id),
                "competitive_strength": "3",
                "notes": "Duplicate relationship test.",
                "csrf_token": second_token,
            },
            headers=self.csrf_headers(second_token),
        )

        self.assertEqual(second_response.status_code, 200)

        connection = self.get_connection()

        try:
            count = connection.execute(
                """
                SELECT COUNT(*)
                FROM competitor_relationships
                WHERE company_id = ?
                  AND competitor_id = ?
                """,
                (
                    self.target_company_id,
                    self.competitor_id,
                ),
            ).fetchone()[0]

            self.assertEqual(count, 1)

        finally:
            connection.close()

    def test_16_invalid_competitor_selection_is_rejected(self):
        self.login_as("Analyst")

        token = self.get_csrf_token()

        response = self.client.post(
            (
                "/competitors/relationships/create/"
                f"{self.target_company_id}"
            ),
            data={
                "competitor_id": "999999",
                "competitive_strength": "3",
                "notes": "Invalid competitor test.",
                "csrf_token": token,
            },
            headers=self.csrf_headers(token),
        )

        self.assertEqual(response.status_code, 200)

        self.assertIsNone(self.get_relationship_id())

    def test_17_invalid_competitive_strength_is_rejected(self):
        self.login_as("Analyst")

        token = self.get_csrf_token()

        response = self.client.post(
            (
                "/competitors/relationships/create/"
                f"{self.target_company_id}"
            ),
            data={
                "competitor_id": str(self.competitor_id),
                "competitive_strength": "9",
                "notes": "Invalid strength test.",
                "csrf_token": token,
            },
            headers=self.csrf_headers(token),
        )

        self.assertEqual(response.status_code, 200)

        self.assertIsNone(self.get_relationship_id())

    def test_18_oversized_relationship_notes_are_rejected(self):
        self.login_as("Analyst")

        token = self.get_csrf_token()

        response = self.client.post(
            (
                "/competitors/relationships/create/"
                f"{self.target_company_id}"
            ),
            data={
                "competitor_id": str(self.competitor_id),
                "competitive_strength": "3",
                "notes": "X" * 2001,
                "csrf_token": token,
            },
            headers=self.csrf_headers(token),
        )

        self.assertEqual(response.status_code, 200)

        self.assertIsNone(self.get_relationship_id())

    # =====================================================
    # 6. RELATIONSHIP UPDATE TESTS
    # =====================================================

    def test_19_relationship_update_succeeds(self):
        self.create_relationship("Analyst")

        relationship_id = self.get_relationship_id()

        self.assertIsNotNone(relationship_id)

        token = self.get_csrf_token()

        response = self.client.post(
            (
                "/competitors/relationships/"
                f"{relationship_id}/update"
            ),
            data={
                f"update-{relationship_id}-competitive_strength": "5",
                f"update-{relationship_id}-notes": (
                    "Updated illustrative relationship notes."
                ),
                f"update-{relationship_id}-csrf_token": token,
            },
            headers=self.csrf_headers(token),
        )

        self.assertEqual(response.status_code, 302)

        connection = self.get_connection()

        try:
            row = connection.execute(
                """
                SELECT competitive_strength, notes
                FROM competitor_relationships
                WHERE id = ?
                """,
                (relationship_id,),
            ).fetchone()

            self.assertEqual(row["competitive_strength"], 5)

            self.assertEqual(
                row["notes"],
                "Updated illustrative relationship notes.",
            )

        finally:
            connection.close()

    def test_20_nonexistent_relationship_update_returns_404(self):
        self.login_as("Analyst")

        token = self.get_csrf_token()

        response = self.client.post(
            "/competitors/relationships/999999/update",
            data={
                "update-999999-competitive_strength": "4",
                "update-999999-notes": "Test",
                "update-999999-csrf_token": token,
            },
            headers=self.csrf_headers(token),
        )

        self.assertEqual(response.status_code, 404)

    # =====================================================
    # 7. RELATIONSHIP DELETION TESTS
    # =====================================================

    def test_21_relationship_deletion_succeeds(self):
        self.create_relationship("Administrator")

        relationship_id = self.get_relationship_id()

        self.assertIsNotNone(relationship_id)

        token = self.get_csrf_token()

        response = self.client.post(
            (
                "/competitors/relationships/"
                f"{relationship_id}/delete"
            ),
            data={
                f"delete-{relationship_id}-csrf_token": token,
            },
            headers=self.csrf_headers(token),
        )

        self.assertEqual(response.status_code, 302)

        self.assertIsNone(self.get_relationship_id())

    def test_22_deletion_preserves_both_companies(self):
        self.create_relationship("Administrator")

        relationship_id = self.get_relationship_id()

        token = self.get_csrf_token()

        self.client.post(
            (
                "/competitors/relationships/"
                f"{relationship_id}/delete"
            ),
            data={
                f"delete-{relationship_id}-csrf_token": token,
            },
            headers=self.csrf_headers(token),
        )

        connection = self.get_connection()

        try:
            target = connection.execute(
                "SELECT id FROM companies WHERE id = ?",
                (self.target_company_id,),
            ).fetchone()

            competitor = connection.execute(
                "SELECT id FROM companies WHERE id = ?",
                (self.competitor_id,),
            ).fetchone()

            self.assertIsNotNone(target)

            self.assertIsNotNone(competitor)

        finally:
            connection.close()

    # =====================================================
    # 8. CSRF TESTS
    # =====================================================

    def test_23_missing_csrf_token_is_rejected(self):
        self.login_as("Analyst")

        response = self.client.post(
            (
                "/competitors/relationships/create/"
                f"{self.target_company_id}"
            ),
            data={
                "competitor_id": str(self.competitor_id),
                "competitive_strength": "3",
                "notes": "Missing CSRF test.",
            },
        )

        self.assertEqual(response.status_code, 400)

        self.assertIsNone(self.get_relationship_id())

    def test_24_invalid_csrf_token_is_rejected(self):
        self.login_as("Analyst")

        response = self.client.post(
            (
                "/competitors/relationships/create/"
                f"{self.target_company_id}"
            ),
            data={
                "competitor_id": str(self.competitor_id),
                "competitive_strength": "3",
                "notes": "Invalid CSRF test.",
                "csrf_token": "invalid-token",
            },
            headers={
                "X-CSRFToken": "invalid-token",
            },
        )

        self.assertEqual(response.status_code, 400)

        self.assertIsNone(self.get_relationship_id())

    # =====================================================
    # 9. SAFE REDIRECT TESTS
    # =====================================================

    def test_25_external_referrer_is_rejected(self):
        self.create_relationship("Analyst")

        relationship_id = self.get_relationship_id()

        token = self.get_csrf_token()

        response = self.client.post(
            (
                "/competitors/relationships/"
                f"{relationship_id}/update"
            ),
            data={
                f"update-{relationship_id}-competitive_strength": "4",
                f"update-{relationship_id}-notes": "Redirect test.",
                f"update-{relationship_id}-csrf_token": token,
            },
            headers={
                **self.csrf_headers(token),
                "Referer": "https://evil.example/phishing",
            },
        )

        self.assertEqual(response.status_code, 302)

        self.assertEqual(
            response.headers["Location"],
            "/competitors/",
        )

    def test_26_same_host_referrer_is_accepted(self):
        self.create_relationship("Analyst")

        relationship_id = self.get_relationship_id()

        token = self.get_csrf_token()

        safe_referrer = (
            "http://localhost/competitors/"
            f"for-company/{self.target_company_id}"
        )

        response = self.client.post(
            (
                "/competitors/relationships/"
                f"{relationship_id}/update"
            ),
            data={
                f"update-{relationship_id}-competitive_strength": "4",
                f"update-{relationship_id}-notes": "Safe redirect test.",
                f"update-{relationship_id}-csrf_token": token,
            },
            headers={
                **self.csrf_headers(token),
                "Referer": safe_referrer,
            },
        )

        self.assertEqual(response.status_code, 302)

        self.assertEqual(
            response.headers["Location"],
            safe_referrer,
        )

    # =====================================================
    # 10. AUDIT LOGGING TESTS
    # =====================================================

    def test_27_create_operation_generates_audit_log(self):
        self.create_relationship("Analyst")

        actions = self.get_audit_actions()

        self.assertTrue(
            any(
                item["action"] == "CREATE"
                and item["entity_type"] == "competitor_relationship"
                for item in actions
            )
        )

    def test_28_update_operation_generates_audit_log(self):
        self.create_relationship("Analyst")

        relationship_id = self.get_relationship_id()

        token = self.get_csrf_token()

        self.client.post(
            (
                "/competitors/relationships/"
                f"{relationship_id}/update"
            ),
            data={
                f"update-{relationship_id}-competitive_strength": "4",
                f"update-{relationship_id}-notes": "Audit update test.",
                f"update-{relationship_id}-csrf_token": token,
            },
            headers=self.csrf_headers(token),
        )

        actions = self.get_audit_actions()

        self.assertTrue(
            any(
                item["action"] == "UPDATE"
                and item["entity_type"] == "competitor_relationship"
                for item in actions
            )
        )

    def test_29_delete_operation_generates_audit_log(self):
        self.create_relationship("Administrator")

        relationship_id = self.get_relationship_id()

        token = self.get_csrf_token()

        self.client.post(
            (
                "/competitors/relationships/"
                f"{relationship_id}/delete"
            ),
            data={
                f"delete-{relationship_id}-csrf_token": token,
            },
            headers=self.csrf_headers(token),
        )

        actions = self.get_audit_actions()

        self.assertTrue(
            any(
                item["action"] == "DELETE"
                and item["entity_type"] == "competitor_relationship"
                for item in actions
            )
        )

    # =====================================================
    # 11. DATABASE INTEGRITY TESTS
    # =====================================================

    def test_30_database_integrity_check(self):
        connection = self.get_connection()

        try:
            result = connection.execute(
                "PRAGMA integrity_check"
            ).fetchone()[0]

            self.assertEqual(result, "ok")

        finally:
            connection.close()

    def test_31_database_foreign_key_check(self):
        connection = self.get_connection()

        try:
            violations = connection.execute(
                "PRAGMA foreign_key_check"
            ).fetchall()

            self.assertEqual(violations, [])

        finally:
            connection.close()

    def test_32_relationship_constraints_are_enforced(self):
        connection = self.get_connection()

        try:
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(
                    """
                    INSERT INTO competitor_relationships (
                        company_id,
                        competitor_id,
                        competitive_strength
                    )
                    VALUES (?, ?, ?)
                    """,
                    (
                        self.target_company_id,
                        self.competitor_id,
                        6,
                    ),
                )

            connection.rollback()

        finally:
            connection.close()


# =========================================================
# TEST RUNNER
# =========================================================

if __name__ == "__main__":

    print("\n")
    print("=" * 65)
    print("STRATEGYSIM - COMPETITOR INTELLIGENCE ROUTE TESTS")
    print("=" * 65)
    print("Database: Isolated temporary SQLite database")
    print("Original project database: NOT MODIFIED")
    print("=" * 65)
    print("\n")

    unittest.main(
        verbosity=2,
        buffer=False,
    )
