
import sqlite3
from datetime import datetime
from urllib.parse import urlsplit

from app.database.connection import get_db
from app.services.audit_service import record_audit_log


# =========================================================
# COMPANY AND INDUSTRY SERVICE EXCEPTIONS
# =========================================================

class IndustryAlreadyExistsError(Exception):
    pass


class IndustryNotFoundError(Exception):
    pass


class CompanyNotFoundError(Exception):
    pass


class InvalidCompanyTypeError(Exception):
    pass


class InvalidCompanyDataError(Exception):
    pass


class InvalidIndustryDataError(Exception):
    pass


# =========================================================
# CONSTANTS
# =========================================================

ALLOWED_COMPANY_TYPES = {
    "Target",
    "Competitor",
    "Other"
}

DEFAULT_GEOGRAPHY = "India"

MAX_NAME_LENGTH = 150
MAX_DESCRIPTION_LENGTH = 5000
MAX_WEBSITE_LENGTH = 500
MAX_HEADQUARTERS_LENGTH = 200
MAX_SECTOR_LENGTH = 150
MAX_GEOGRAPHY_LENGTH = 100


# =========================================================
# COMMON VALIDATION HELPERS
# =========================================================

def _clean_text(value, field_name, required=False, max_length=None):

    if value is None:
        value = ""

    if not isinstance(value, str):
        value = str(value)

    value = value.strip()

    if required and not value:
        raise ValueError(f"{field_name} cannot be empty.")

    if max_length is not None and len(value) > max_length:
        raise ValueError(
            f"{field_name} cannot exceed {max_length} characters."
        )

    return value or None


def _optional_float(value, field_name, minimum=None, maximum=None):

    if value is None or value == "":
        return None

    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be a valid number.")

    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field_name} must be a valid number.")

    if not number >= 0 and minimum == 0:
        raise ValueError(f"{field_name} cannot be negative.")

    if minimum is not None and number < minimum:
        raise ValueError(
            f"{field_name} cannot be less than {minimum}."
        )

    if maximum is not None and number > maximum:
        raise ValueError(
            f"{field_name} cannot exceed {maximum}."
        )

    return number


def _optional_integer(value, field_name, minimum=None, maximum=None):

    if value is None or value == "":
        return None

    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be a whole number.")

    try:
        number = int(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field_name} must be a whole number.")

    if str(value).strip() not in (str(number), f"+{number}"):
        raise ValueError(f"{field_name} must be a whole number.")

    if minimum is not None and number < minimum:
        raise ValueError(
            f"{field_name} cannot be less than {minimum}."
        )

    if maximum is not None and number > maximum:
        raise ValueError(
            f"{field_name} cannot exceed {maximum}."
        )

    return number


def _validate_website(value):

    website = _clean_text(
        value,
        "Website",
        max_length=MAX_WEBSITE_LENGTH
    )

    if website is None:
        return None

    try:
        parsed = urlsplit(website)

        if (
            parsed.scheme.lower() not in {"http", "https"}
            or not parsed.netloc
            or "." not in parsed.hostname
        ):
            raise ValueError

    except (ValueError, AttributeError):
        raise ValueError(
            "Enter a valid website URL beginning with "
            "http:// or https://."
        )

    return website


# =========================================================
# INDUSTRY VALIDATION
# =========================================================

def _validate_industry_data(
    name,
    sector=None,
    description=None,
    geography=DEFAULT_GEOGRAPHY,
    industry_type=None
):

    name = _clean_text(
        name,
        "Industry name",
        required=True,
        max_length=MAX_NAME_LENGTH
    )

    sector = _clean_text(
        sector,
        "Industry sector",
        max_length=MAX_SECTOR_LENGTH
    )

    description = _clean_text(
        description,
        "Industry description",
        max_length=MAX_DESCRIPTION_LENGTH
    )

    geography = _clean_text(
        geography or DEFAULT_GEOGRAPHY,
        "Geography",
        required=True,
        max_length=MAX_GEOGRAPHY_LENGTH
    )

    industry_type = _clean_text(
        industry_type,
        "Industry type",
        max_length=MAX_SECTOR_LENGTH
    )

    return {
        "name": name,
        "sector": sector,
        "description": description,
        "geography": geography,
        "industry_type": industry_type
    }


# =========================================================
# COMPANY VALIDATION
# =========================================================

def _validate_company_data(
    name,
    industry_id,
    company_type="Target",
    description=None,
    headquarters=None,
    website=None,
    annual_revenue=None,
    employee_count=None,
    market_share=None,
    founded_year=None
):

    name = _clean_text(
        name,
        "Company name",
        required=True,
        max_length=MAX_NAME_LENGTH
    )

    try:
        industry_id = int(industry_id)
    except (TypeError, ValueError):
        raise ValueError("Select a valid industry.")

    if industry_id < 1:
        raise ValueError("Select a valid industry.")

    if company_type not in ALLOWED_COMPANY_TYPES:
        raise InvalidCompanyTypeError(
            "The selected company type is invalid."
        )

    description = _clean_text(
        description,
        "Company description",
        max_length=MAX_DESCRIPTION_LENGTH
    )

    headquarters = _clean_text(
        headquarters,
        "Headquarters",
        max_length=MAX_HEADQUARTERS_LENGTH
    )

    website = _validate_website(website)

    annual_revenue = _optional_float(
        annual_revenue,
        "Annual revenue",
        minimum=0
    )

    employee_count = _optional_integer(
        employee_count,
        "Employee count",
        minimum=0
    )

    market_share = _optional_float(
        market_share,
        "Market share",
        minimum=0,
        maximum=100
    )

    founded_year = _optional_integer(
        founded_year,
        "Founded year",
        minimum=1800,
        maximum=datetime.now().year
    )

    return {
        "name": name,
        "industry_id": industry_id,
        "company_type": company_type,
        "description": description,
        "headquarters": headquarters,
        "website": website,
        "annual_revenue": annual_revenue,
        "employee_count": employee_count,
        "market_share": market_share,
        "founded_year": founded_year
    }


# =========================================================
# INDUSTRY DIRECTORY
# =========================================================

def get_industries(search=None, geography=None):

    database = get_db()

    query = """
        SELECT
            industries.id,
            industries.name,
            industries.sector,
            industries.description,
            industries.geography,
            industries.industry_type,
            industries.created_at,
            industries.updated_at,
            COUNT(companies.id) AS company_count
        FROM industries
        LEFT JOIN companies
            ON companies.industry_id = industries.id
        WHERE 1 = 1
    """

    parameters = []

    if search and str(search).strip():

        query += """
            AND (
                industries.name LIKE ?
                OR industries.sector LIKE ?
            )
        """

        search_value = f"%{str(search).strip()}%"

        parameters.extend([
            search_value,
            search_value
        ])

    if geography and str(geography).strip():

        query += """
            AND industries.geography = ?
        """

        parameters.append(str(geography).strip())

    query += """
        GROUP BY industries.id
        ORDER BY industries.name COLLATE NOCASE ASC
    """

    rows = database.execute(
        query,
        parameters
    ).fetchall()

    return [dict(row) for row in rows]


# =========================================================
# GET INDUSTRY DETAILS
# =========================================================

def get_industry_details(industry_id):

    try:
        industry_id = int(industry_id)
    except (TypeError, ValueError):
        return None

    database = get_db()

    row = database.execute(
        """
        SELECT
            industries.id,
            industries.name,
            industries.sector,
            industries.description,
            industries.geography,
            industries.industry_type,
            industries.created_at,
            industries.updated_at,
            COUNT(companies.id) AS company_count
        FROM industries
        LEFT JOIN companies
            ON companies.industry_id = industries.id
        WHERE industries.id = ?
        GROUP BY industries.id
        """,
        (industry_id,)
    ).fetchone()

    if row is None:
        return None

    return dict(row)


# =========================================================
# CREATE INDUSTRY
# =========================================================

def create_industry(
    name,
    created_by,
    sector=None,
    description=None,
    geography=DEFAULT_GEOGRAPHY,
    industry_type=None
):

    try:
        created_by = int(created_by)
    except (TypeError, ValueError):
        raise ValueError("Invalid user identifier.")

    data = _validate_industry_data(
        name=name,
        sector=sector,
        description=description,
        geography=geography,
        industry_type=industry_type
    )

    database = get_db()

    try:
        database.execute("BEGIN IMMEDIATE")

        existing = database.execute(
            """
            SELECT id
            FROM industries
            WHERE name = ?
              AND geography = ?
            LIMIT 1
            """,
            (
                data["name"],
                data["geography"]
            )
        ).fetchone()

        if existing:
            raise IndustryAlreadyExistsError(
                "An industry with this name already exists "
                "for the selected geography."
            )

        cursor = database.execute(
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
                data["name"],
                data["sector"],
                data["description"],
                data["geography"],
                data["industry_type"]
            )
        )

        industry_id = cursor.lastrowid

        record_audit_log(
            user_id=created_by,
            action="INDUSTRY_CREATED",
            entity_type="Industry",
            entity_id=industry_id,
            description=(
                f"Created industry '{data['name']}' "
                f"for geography '{data['geography']}'."
            ),
            commit=False
        )

        database.commit()

        return industry_id

    except sqlite3.IntegrityError as error:
        database.rollback()

        if "industries.name" in str(error).lower():
            raise IndustryAlreadyExistsError(
                "An industry with this name already exists "
                "for the selected geography."
            ) from error

        raise

    except Exception:
        database.rollback()
        raise


# =========================================================
# UPDATE INDUSTRY
# =========================================================

def update_industry(
    industry_id,
    name,
    acting_user_id,
    sector=None,
    description=None,
    geography=DEFAULT_GEOGRAPHY,
    industry_type=None
):

    try:
        industry_id = int(industry_id)
        acting_user_id = int(acting_user_id)
    except (TypeError, ValueError):
        raise ValueError("Invalid industry or user identifier.")

    data = _validate_industry_data(
        name=name,
        sector=sector,
        description=description,
        geography=geography,
        industry_type=industry_type
    )

    database = get_db()

    try:
        database.execute("BEGIN IMMEDIATE")

        existing_industry = database.execute(
            """
            SELECT id, name, geography
            FROM industries
            WHERE id = ?
            """,
            (industry_id,)
        ).fetchone()

        if existing_industry is None:
            raise IndustryNotFoundError(
                "The requested industry does not exist."
            )

        duplicate = database.execute(
            """
            SELECT id
            FROM industries
            WHERE name = ?
              AND geography = ?
              AND id != ?
            LIMIT 1
            """,
            (
                data["name"],
                data["geography"],
                industry_id
            )
        ).fetchone()

        if duplicate:
            raise IndustryAlreadyExistsError(
                "Another industry with this name already exists "
                "for the selected geography."
            )

        database.execute(
            """
            UPDATE industries
            SET
                name = ?,
                sector = ?,
                description = ?,
                geography = ?,
                industry_type = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                data["name"],
                data["sector"],
                data["description"],
                data["geography"],
                data["industry_type"],
                industry_id
            )
        )

        record_audit_log(
            user_id=acting_user_id,
            action="INDUSTRY_UPDATED",
            entity_type="Industry",
            entity_id=industry_id,
            description=(
                f"Updated industry '{existing_industry['name']}' "
                f"(ID: {industry_id})."
            ),
            commit=False
        )

        database.commit()

        return True

    except sqlite3.IntegrityError as error:
        database.rollback()

        if "industries.name" in str(error).lower():
            raise IndustryAlreadyExistsError(
                "Another industry with this name already exists "
                "for the selected geography."
            ) from error

        raise

    except Exception:
        database.rollback()
        raise


# =========================================================
# COMPANY DIRECTORY
# =========================================================

def get_companies(
    search=None,
    industry_id=None,
    company_type=None,
    limit=100,
    offset=0
):

    try:
        limit = int(limit)
        offset = int(offset)
    except (TypeError, ValueError):
        raise ValueError("Invalid company pagination values.")

    if limit < 1 or limit > 500:
        raise ValueError("Company limit must be between 1 and 500.")

    if offset < 0:
        raise ValueError("Company offset cannot be negative.")

    if company_type and company_type not in ALLOWED_COMPANY_TYPES:
        raise InvalidCompanyTypeError(
            "The selected company type is invalid."
        )

    database = get_db()

    query = """
        SELECT
            companies.id,
            companies.industry_id,
            industries.name AS industry_name,
            companies.name,
            companies.company_type,
            companies.description,
            companies.headquarters,
            companies.website,
            companies.annual_revenue,
            companies.employee_count,
            companies.market_share,
            companies.founded_year,
            companies.is_demo,
            companies.created_by,
            companies.created_at,
            companies.updated_at
        FROM companies
        INNER JOIN industries
            ON industries.id = companies.industry_id
        WHERE 1 = 1
    """

    parameters = []

    if search and str(search).strip():

        query += """
            AND (
                companies.name LIKE ?
                OR companies.description LIKE ?
                OR companies.headquarters LIKE ?
                OR industries.name LIKE ?
            )
        """

        search_value = f"%{str(search).strip()}%"

        parameters.extend([
            search_value,
            search_value,
            search_value,
            search_value
        ])

    if industry_id is not None and industry_id != "":

        try:
            industry_id = int(industry_id)
        except (TypeError, ValueError):
            raise ValueError("Invalid industry filter.")

        query += """
            AND companies.industry_id = ?
        """

        parameters.append(industry_id)

    if company_type:

        query += """
            AND companies.company_type = ?
        """

        parameters.append(company_type)

    query += """
        ORDER BY companies.name COLLATE NOCASE ASC
        LIMIT ?
        OFFSET ?
    """

    parameters.extend([
        limit,
        offset
    ])

    rows = database.execute(
        query,
        parameters
    ).fetchall()

    return [dict(row) for row in rows]


# =========================================================
# GET COMPANY DETAILS
# =========================================================

def get_company_details(company_id):

    try:
        company_id = int(company_id)
    except (TypeError, ValueError):
        return None

    database = get_db()

    row = database.execute(
        """
        SELECT
            companies.id,
            companies.industry_id,
            industries.name AS industry_name,
            industries.sector AS industry_sector,
            industries.geography AS industry_geography,
            companies.name,
            companies.company_type,
            companies.description,
            companies.headquarters,
            companies.website,
            companies.annual_revenue,
            companies.employee_count,
            companies.market_share,
            companies.founded_year,
            companies.is_demo,
            companies.created_by,
            companies.created_at,
            companies.updated_at
        FROM companies
        INNER JOIN industries
            ON industries.id = companies.industry_id
        WHERE companies.id = ?
        """,
        (company_id,)
    ).fetchone()

    if row is None:
        return None

    result = dict(row)

    result["is_demo"] = bool(result["is_demo"])

    return result


# =========================================================
# CREATE COMPANY
# =========================================================

def create_company(
    name,
    industry_id,
    created_by,
    company_type="Target",
    description=None,
    headquarters=None,
    website=None,
    annual_revenue=None,
    employee_count=None,
    market_share=None,
    founded_year=None,
    is_demo=False
):

    try:
        created_by = int(created_by)
    except (TypeError, ValueError):
        raise ValueError("Invalid user identifier.")

    if not isinstance(is_demo, bool):
        raise ValueError("Invalid demonstration data setting.")

    data = _validate_company_data(
        name=name,
        industry_id=industry_id,
        company_type=company_type,
        description=description,
        headquarters=headquarters,
        website=website,
        annual_revenue=annual_revenue,
        employee_count=employee_count,
        market_share=market_share,
        founded_year=founded_year
    )

    database = get_db()

    try:
        database.execute("BEGIN IMMEDIATE")

        industry = database.execute(
            """
            SELECT id, name
            FROM industries
            WHERE id = ?
            """,
            (data["industry_id"],)
        ).fetchone()

        if industry is None:
            raise IndustryNotFoundError(
                "The selected industry does not exist."
            )

        cursor = database.execute(
            """
            INSERT INTO companies (
                industry_id,
                name,
                company_type,
                description,
                headquarters,
                website,
                annual_revenue,
                employee_count,
                market_share,
                founded_year,
                is_demo,
                created_by
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                data["industry_id"],
                data["name"],
                data["company_type"],
                data["description"],
                data["headquarters"],
                data["website"],
                data["annual_revenue"],
                data["employee_count"],
                data["market_share"],
                data["founded_year"],
                1 if is_demo else 0,
                created_by
            )
        )

        company_id = cursor.lastrowid

        record_audit_log(
            user_id=created_by,
            action="COMPANY_CREATED",
            entity_type="Company",
            entity_id=company_id,
            description=(
                f"Created {data['company_type']} company "
                f"'{data['name']}' under industry "
                f"'{industry['name']}'. "
                f"Illustrative demonstration record: "
                f"{'Yes' if is_demo else 'No'}."
            ),
            commit=False
        )

        database.commit()

        return company_id

    except Exception:
        database.rollback()
        raise


# =========================================================
# UPDATE COMPANY
# =========================================================

def update_company(
    company_id,
    name,
    industry_id,
    acting_user_id,
    company_type="Target",
    description=None,
    headquarters=None,
    website=None,
    annual_revenue=None,
    employee_count=None,
    market_share=None,
    founded_year=None,
    is_demo=False
):

    try:
        company_id = int(company_id)
        acting_user_id = int(acting_user_id)
    except (TypeError, ValueError):
        raise ValueError("Invalid company or user identifier.")

    if not isinstance(is_demo, bool):
        raise ValueError("Invalid demonstration data setting.")

    data = _validate_company_data(
        name=name,
        industry_id=industry_id,
        company_type=company_type,
        description=description,
        headquarters=headquarters,
        website=website,
        annual_revenue=annual_revenue,
        employee_count=employee_count,
        market_share=market_share,
        founded_year=founded_year
    )

    database = get_db()

    try:
        database.execute("BEGIN IMMEDIATE")

        existing_company = database.execute(
            """
            SELECT id, name
            FROM companies
            WHERE id = ?
            """,
            (company_id,)
        ).fetchone()

        if existing_company is None:
            raise CompanyNotFoundError(
                "The requested company does not exist."
            )

        industry = database.execute(
            """
            SELECT id, name
            FROM industries
            WHERE id = ?
            """,
            (data["industry_id"],)
        ).fetchone()

        if industry is None:
            raise IndustryNotFoundError(
                "The selected industry does not exist."
            )

        database.execute(
            """
            UPDATE companies
            SET
                industry_id = ?,
                name = ?,
                company_type = ?,
                description = ?,
                headquarters = ?,
                website = ?,
                annual_revenue = ?,
                employee_count = ?,
                market_share = ?,
                founded_year = ?,
                is_demo = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                data["industry_id"],
                data["name"],
                data["company_type"],
                data["description"],
                data["headquarters"],
                data["website"],
                data["annual_revenue"],
                data["employee_count"],
                data["market_share"],
                data["founded_year"],
                1 if is_demo else 0,
                company_id
            )
        )

        record_audit_log(
            user_id=acting_user_id,
            action="COMPANY_UPDATED",
            entity_type="Company",
            entity_id=company_id,
            description=(
                f"Updated company '{existing_company['name']}' "
                f"(ID: {company_id})."
            ),
            commit=False
        )

        database.commit()

        return True

    except Exception:
        database.rollback()
        raise
