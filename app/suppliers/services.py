
"""
Supplier Network Services

Business logic for:
- Supplier management and hierarchy
- Supplier relationships
- Component management
- Supplier-component mappings
- Supplier facilities
- Procurement records

All write operations are transactional and audited.
"""

from app.database.connection import get_db
from app.services.audit_service import record_audit_log


# =========================================================
# EXCEPTIONS
# =========================================================

class SupplierError(Exception):
    """Base exception for Supplier Network operations."""


class SupplierValidationError(SupplierError):
    """Raised when supplied data is invalid."""


class SupplierNotFoundError(SupplierError):
    """Raised when a supplier cannot be found."""


class ComponentNotFoundError(SupplierError):
    """Raised when a component cannot be found."""


class SupplierRelationshipError(SupplierError):
    """Raised when a supplier relationship is invalid."""


class SupplierComponentError(SupplierError):
    """Raised when a supplier-component mapping is invalid."""


class FacilityNotFoundError(SupplierError):
    """Raised when a facility cannot be found."""


class ProcurementRecordNotFoundError(SupplierError):
    """Raised when a procurement record cannot be found."""


# =========================================================
# CONSTANTS
# =========================================================

RISK_LEVELS = {"Low", "Medium", "High", "Critical"}

COMPONENT_CRITICALITY_LEVELS = {
    "Low", "Medium", "High", "Critical"
}

CONTRACT_STATUSES = {
    "Active", "Expired", "Pending", "Terminated"
}

FACILITY_STATUSES = {
    "Active", "Inactive", "Disrupted"
}


# =========================================================
# COMMON VALIDATION
# =========================================================

def _required_text(value, field_name, maximum=255):
    if not isinstance(value, str) or not value.strip():
        raise SupplierValidationError(
            f"{field_name} is required."
        )

    value = value.strip()

    if len(value) > maximum:
        raise SupplierValidationError(
            f"{field_name} cannot exceed {maximum} characters."
        )

    return value


def _optional_text(value, field_name, maximum=1000):
    if value is None:
        return None

    if not isinstance(value, str):
        raise SupplierValidationError(
            f"{field_name} must be text."
        )

    value = value.strip()

    if not value:
        return None

    if len(value) > maximum:
        raise SupplierValidationError(
            f"{field_name} cannot exceed {maximum} characters."
        )

    return value


def _positive_id(value, field_name):
    try:
        value = int(value)
    except (TypeError, ValueError):
        raise SupplierValidationError(
            f"{field_name} must be a valid ID."
        )

    if value <= 0:
        raise SupplierValidationError(
            f"{field_name} must be positive."
        )

    return value


def _optional_number(
    value,
    field_name,
    minimum=None,
    maximum=None,
    integer=False
):
    if value in (None, ""):
        return None

    try:
        number = int(value) if integer else float(value)
    except (TypeError, ValueError):
        raise SupplierValidationError(
            f"{field_name} must be a valid number."
        )

    if number != number or number in (float("inf"), float("-inf")):
        raise SupplierValidationError(
            f"{field_name} must be finite."
        )

    if minimum is not None and number < minimum:
        raise SupplierValidationError(
            f"{field_name} cannot be less than {minimum}."
        )

    if maximum is not None and number > maximum:
        raise SupplierValidationError(
            f"{field_name} cannot exceed {maximum}."
        )

    return number


def _required_choice(value, choices, field_name):
    if value not in choices:
        raise SupplierValidationError(
            f"Select a valid {field_name}."
        )

    return value


def _boolean(value, field_name):
    if value in (True, 1, "1", "true", "True", "on"):
        return 1

    if value in (False, 0, "0", "false", "False", "", None):
        return 0

    raise SupplierValidationError(
        f"{field_name} must be true or false."
    )


def _row_to_dict(row):
    return dict(row) if row is not None else None


def _get_supplier_or_raise(database, supplier_id):
    supplier_id = _positive_id(
        supplier_id,
        "Supplier ID"
    )

    row = database.execute(
        "SELECT * FROM suppliers WHERE id = ?",
        (supplier_id,)
    ).fetchone()

    if row is None:
        raise SupplierNotFoundError(
            "Supplier record not found."
        )

    return row


def _get_component_or_raise(database, component_id):
    component_id = _positive_id(
        component_id,
        "Component ID"
    )

    row = database.execute(
        "SELECT * FROM components WHERE id = ?",
        (component_id,)
    ).fetchone()

    if row is None:
        raise ComponentNotFoundError(
            "Component record not found."
        )

    return row


def _audit(
    user_id,
    action,
    entity_type,
    entity_id,
    description
):
    record_audit_log(
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        description=description,
        commit=False
    )


# =========================================================
# SUPPLIER MANAGEMENT
# =========================================================

def create_supplier(
    acting_user_id,
    name,
    supplier_code=None,
    parent_supplier_id=None,
    country=None,
    headquarters=None,
    supplier_type=None,
    tier_level=1,
    risk_level="Medium",
    financial_dependency_score=None,
    operational_risk_score=None,
    is_active=True,
    description=None
):
    """Create a supplier record."""

    acting_user_id = _positive_id(
        acting_user_id,
        "Acting user ID"
    )

    name = _required_text(name, "Supplier name")
    supplier_code = _optional_text(
        supplier_code, "Supplier code"
    )
    country = _optional_text(country, "Country")
    headquarters = _optional_text(
        headquarters, "Headquarters"
    )
    supplier_type = _optional_text(
        supplier_type, "Supplier type"
    )
    description = _optional_text(
        description, "Description", 5000
    )

    tier_level = _optional_number(
        tier_level,
        "Tier level",
        minimum=1,
        integer=True
    )

    if tier_level is None:
        tier_level = 1

    risk_level = _required_choice(
        risk_level,
        RISK_LEVELS,
        "risk level"
    )

    financial_dependency_score = _optional_number(
        financial_dependency_score,
        "Financial dependency score",
        minimum=0,
        maximum=100
    )

    operational_risk_score = _optional_number(
        operational_risk_score,
        "Operational risk score",
        minimum=0,
        maximum=100
    )

    is_active = _boolean(is_active, "Active status")

    if parent_supplier_id not in (None, ""):
        parent_supplier_id = _positive_id(
            parent_supplier_id,
            "Parent supplier ID"
        )

        if parent_supplier_id is not None:
            if parent_supplier_id <= 0:
                raise SupplierValidationError(
                    "Invalid parent supplier."
                )

    else:
        parent_supplier_id = None

    database = get_db()

    try:
        with database:
            if parent_supplier_id is not None:
                _get_supplier_or_raise(
                    database,
                    parent_supplier_id
                )

            cursor = database.execute(
                """
                INSERT INTO suppliers (
                    name,
                    supplier_code,
                    parent_supplier_id,
                    country,
                    headquarters,
                    supplier_type,
                    tier_level,
                    risk_level,
                    financial_dependency_score,
                    operational_risk_score,
                    is_active,
                    description
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    name,
                    supplier_code,
                    parent_supplier_id,
                    country,
                    headquarters,
                    supplier_type,
                    tier_level,
                    risk_level,
                    financial_dependency_score,
                    operational_risk_score,
                    is_active,
                    description
                )
            )

            supplier_id = cursor.lastrowid

            _audit(
                acting_user_id,
                "CREATE",
                "Supplier",
                supplier_id,
                f"Created supplier: {name}"
            )

        return get_supplier_details(supplier_id)

    except SupplierError:
        raise

    except Exception as exc:
        if "UNIQUE constraint failed" in str(exc):
            raise SupplierValidationError(
                "This supplier code is already in use."
            ) from exc
        raise


def get_supplier_details(supplier_id):
    database = get_db()

    supplier = _get_supplier_or_raise(
        database,
        supplier_id
    )

    result = dict(supplier)

    result["parent_supplier"] = None

    if result["parent_supplier_id"]:
        parent = database.execute(
            """
            SELECT id, name, supplier_code
            FROM suppliers
            WHERE id = ?
            """,
            (result["parent_supplier_id"],)
        ).fetchone()

        result["parent_supplier"] = _row_to_dict(parent)

    result["child_suppliers"] = [
        dict(row)
        for row in database.execute(
            """
            SELECT id, name, supplier_code, tier_level, risk_level
            FROM suppliers
            WHERE parent_supplier_id = ?
            ORDER BY name
            """,
            (result["id"],)
        ).fetchall()
    ]

    result["component_count"] = database.execute(
        """
        SELECT COUNT(*)
        FROM supplier_components
        WHERE supplier_id = ?
        """,
        (result["id"],)
    ).fetchone()[0]

    result["facility_count"] = database.execute(
        """
        SELECT COUNT(*)
        FROM facilities
        WHERE supplier_id = ?
        """,
        (result["id"],)
    ).fetchone()[0]

    return result


def get_supplier_records(
    search=None,
    risk_level=None,
    supplier_type=None,
    tier_level=None,
    active_only=False,
    limit=100,
    offset=0
):
    """Return filtered supplier records."""

    try:
        limit = int(limit)
        offset = int(offset)
    except (TypeError, ValueError):
        raise SupplierValidationError(
            "Invalid pagination values."
        )

    if limit < 1 or limit > 500 or offset < 0:
        raise SupplierValidationError(
            "Invalid pagination range."
        )

    conditions = []
    parameters = []

    if search:
        search = _optional_text(search, "Search", 255)
        if search:
            conditions.append(
                """
                (
                    name LIKE ?
                    OR supplier_code LIKE ?
                    OR country LIKE ?
                    OR headquarters LIKE ?
                )
                """
            )
            term = f"%{search}%"
            parameters.extend([term, term, term, term])

    if risk_level:
        conditions.append("risk_level = ?")
        parameters.append(
            _required_choice(
                risk_level,
                RISK_LEVELS,
                "risk level"
            )
        )

    if supplier_type:
        conditions.append("supplier_type = ?")
        parameters.append(
            _optional_text(supplier_type, "Supplier type")
        )

    if tier_level not in (None, ""):
        conditions.append("tier_level = ?")
        parameters.append(
            _optional_number(
                tier_level,
                "Tier level",
                minimum=1,
                integer=True
            )
        )

    if active_only:
        conditions.append("suppliers.is_active = 1")

    where_clause = (
        "WHERE " + " AND ".join(conditions)
        if conditions else ""
    )

    database = get_db()

    rows = database.execute(
        f"""
        SELECT
            suppliers.*,
            parent.name AS parent_supplier_name,
            (
                SELECT COUNT(*)
                FROM supplier_components sc
                WHERE sc.supplier_id = suppliers.id
            ) AS component_count,
            (
                SELECT COUNT(*)
                FROM facilities f
                WHERE f.supplier_id = suppliers.id
            ) AS facility_count
        FROM suppliers
        LEFT JOIN suppliers parent
            ON parent.id = suppliers.parent_supplier_id
        {where_clause}
        ORDER BY suppliers.name COLLATE NOCASE
        LIMIT ? OFFSET ?
        """,
        (*parameters, limit, offset)
    ).fetchall()

    return [dict(row) for row in rows]


def update_supplier(
    supplier_id,
    acting_user_id,
    updates
):
    """Update an existing supplier."""

    supplier_id = _positive_id(
        supplier_id, "Supplier ID"
    )
    acting_user_id = _positive_id(
        acting_user_id, "Acting user ID"
    )

    if not isinstance(updates, dict) or not updates:
        raise SupplierValidationError(
            "No supplier updates were provided."
        )

    allowed_fields = {
        "name",
        "supplier_code",
        "parent_supplier_id",
        "country",
        "headquarters",
        "supplier_type",
        "tier_level",
        "risk_level",
        "financial_dependency_score",
        "operational_risk_score",
        "is_active",
        "description"
    }

    if not set(updates).issubset(allowed_fields):
        raise SupplierValidationError(
            "One or more supplier fields are not editable."
        )

    cleaned = {}

    for field, value in updates.items():
        if field == "name":
            cleaned[field] = _required_text(
                value, "Supplier name"
            )
        elif field in {
            "supplier_code", "country",
            "headquarters", "supplier_type"
        }:
            cleaned[field] = _optional_text(
                value, field.replace("_", " ").title()
            )
        elif field == "description":
            cleaned[field] = _optional_text(
                value, "Description", 5000
            )
        elif field == "parent_supplier_id":
            cleaned[field] = (
                _positive_id(value, "Parent supplier ID")
                if value not in (None, "")
                else None
            )
        elif field == "tier_level":
            cleaned[field] = _optional_number(
                value, "Tier level", minimum=1, integer=True
            )
        elif field == "risk_level":
            cleaned[field] = _required_choice(
                value, RISK_LEVELS, "risk level"
            )
        elif field in {
            "financial_dependency_score",
            "operational_risk_score"
        }:
            cleaned[field] = _optional_number(
                value, field.replace("_", " ").title(),
                minimum=0, maximum=100
            )
        elif field == "is_active":
            cleaned[field] = _boolean(value, "Active status")

    database = get_db()

    try:
        with database:
            _get_supplier_or_raise(database, supplier_id)

            if cleaned.get("parent_supplier_id") is not None:
                parent_id = cleaned["parent_supplier_id"]

                if parent_id == supplier_id:
                    raise SupplierValidationError(
                        "A supplier cannot be its own parent."
                    )

                _get_supplier_or_raise(database, parent_id)

                # Prevent a circular hierarchy.
                current_id = parent_id
                visited = set()

                while current_id is not None:
                    if current_id == supplier_id:
                        raise SupplierValidationError(
                            "This parent selection would create a supplier hierarchy cycle."
                        )

                    if current_id in visited:
                        raise SupplierValidationError(
                            "The existing supplier hierarchy contains a cycle."
                        )

                    visited.add(current_id)

                    parent_row = database.execute(
                        """
                        SELECT parent_supplier_id
                        FROM suppliers
                        WHERE id = ?
                        """,
                        (current_id,)
                    ).fetchone()

                    current_id = (
                        parent_row["parent_supplier_id"]
                        if parent_row else None
                    )

            assignments = ", ".join(
                f"{field} = ?" for field in cleaned
            )

            database.execute(
                f"""
                UPDATE suppliers
                SET {assignments},
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (*cleaned.values(), supplier_id)
            )

            _audit(
                acting_user_id,
                "UPDATE",
                "Supplier",
                supplier_id,
                "Updated supplier record."
            )

        return get_supplier_details(supplier_id)

    except SupplierError:
        raise

    except Exception as exc:
        if "UNIQUE constraint failed" in str(exc):
            raise SupplierValidationError(
                "This supplier code is already in use."
            ) from exc
        raise


def delete_supplier(supplier_id, acting_user_id):
    """Delete a supplier, respecting procurement restrictions."""

    supplier_id = _positive_id(
        supplier_id, "Supplier ID"
    )
    acting_user_id = _positive_id(
        acting_user_id, "Acting user ID"
    )

    database = get_db()

    try:
        with database:
            supplier = _get_supplier_or_raise(
                database, supplier_id
            )

            supplier_name = supplier["name"]

            procurement_count = database.execute(
                """
                SELECT COUNT(*)
                FROM procurement_records
                WHERE supplier_id = ?
                """,
                (supplier_id,)
            ).fetchone()[0]

            if procurement_count:
                raise SupplierValidationError(
                    "This supplier has procurement records and cannot be deleted. "
                    "Deactivate it instead."
                )

            database.execute(
                "DELETE FROM suppliers WHERE id = ?",
                (supplier_id,)
            )

            _audit(
                acting_user_id,
                "DELETE",
                "Supplier",
                supplier_id,
                f"Deleted supplier: {supplier_name}"
            )

        return True

    except SupplierError:
        raise


# =========================================================
# SUPPLIER RELATIONSHIPS
# =========================================================

def create_supplier_relationship(
    acting_user_id,
    source_supplier_id,
    target_supplier_id,
    relationship_type,
    dependency_strength=None,
    description=None
):
    acting_user_id = _positive_id(
        acting_user_id, "Acting user ID"
    )
    source_supplier_id = _positive_id(
        source_supplier_id, "Source supplier ID"
    )
    target_supplier_id = _positive_id(
        target_supplier_id, "Target supplier ID"
    )

    if source_supplier_id == target_supplier_id:
        raise SupplierRelationshipError(
            "A supplier cannot have a relationship with itself."
        )

    relationship_type = _required_text(
        relationship_type, "Relationship type"
    )
    dependency_strength = _optional_number(
        dependency_strength,
        "Dependency strength",
        minimum=0,
        maximum=100
    )
    description = _optional_text(
        description, "Description", 5000
    )

    database = get_db()

    try:
        with database:
            _get_supplier_or_raise(
                database, source_supplier_id
            )
            _get_supplier_or_raise(
                database, target_supplier_id
            )

            cursor = database.execute(
                """
                INSERT INTO supplier_relationships (
                    source_supplier_id,
                    target_supplier_id,
                    relationship_type,
                    dependency_strength,
                    description
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    source_supplier_id,
                    target_supplier_id,
                    relationship_type,
                    dependency_strength,
                    description
                )
            )

            relationship_id = cursor.lastrowid

            _audit(
                acting_user_id,
                "CREATE",
                "SupplierRelationship",
                relationship_id,
                "Created supplier relationship."
            )

        return get_supplier_relationship(relationship_id)

    except SupplierError:
        raise

    except Exception as exc:
        if "UNIQUE constraint failed" in str(exc):
            raise SupplierRelationshipError(
                "This supplier relationship already exists."
            ) from exc
        raise


def get_supplier_relationship(relationship_id):
    relationship_id = _positive_id(
        relationship_id, "Relationship ID"
    )

    row = get_db().execute(
        """
        SELECT
            sr.*,
            source.name AS source_supplier_name,
            target.name AS target_supplier_name
        FROM supplier_relationships sr
        JOIN suppliers source
            ON source.id = sr.source_supplier_id
        JOIN suppliers target
            ON target.id = sr.target_supplier_id
        WHERE sr.id = ?
        """,
        (relationship_id,)
    ).fetchone()

    if row is None:
        raise SupplierRelationshipError(
            "Supplier relationship not found."
        )

    return dict(row)


def get_supplier_relationships(supplier_id=None):
    database = get_db()

    query = """
        SELECT
            sr.*,
            source.name AS source_supplier_name,
            target.name AS target_supplier_name
        FROM supplier_relationships sr
        JOIN suppliers source
            ON source.id = sr.source_supplier_id
        JOIN suppliers target
            ON target.id = sr.target_supplier_id
    """

    parameters = ()

    if supplier_id is not None:
        supplier_id = _positive_id(
            supplier_id, "Supplier ID"
        )
        query += """
            WHERE sr.source_supplier_id = ?
               OR sr.target_supplier_id = ?
        """
        parameters = (supplier_id, supplier_id)

    query += " ORDER BY sr.id DESC"

    return [
        dict(row)
        for row in database.execute(
            query, parameters
        ).fetchall()
    ]


def delete_supplier_relationship(
    relationship_id,
    acting_user_id
):
    relationship_id = _positive_id(
        relationship_id, "Relationship ID"
    )
    acting_user_id = _positive_id(
        acting_user_id, "Acting user ID"
    )

    database = get_db()

    with database:
        row = database.execute(
            """
            SELECT id
            FROM supplier_relationships
            WHERE id = ?
            """,
            (relationship_id,)
        ).fetchone()

        if row is None:
            raise SupplierRelationshipError(
                "Supplier relationship not found."
            )

        database.execute(
            """
            DELETE FROM supplier_relationships
            WHERE id = ?
            """,
            (relationship_id,)
        )

        _audit(
            acting_user_id,
            "DELETE",
            "SupplierRelationship",
            relationship_id,
            "Deleted supplier relationship."
        )

    return True


# =========================================================
# COMPONENT MANAGEMENT
# =========================================================

def create_component(
    acting_user_id,
    name,
    component_code=None,
    category=None,
    description=None,
    criticality="Medium",
    is_active=True
):
    acting_user_id = _positive_id(
        acting_user_id, "Acting user ID"
    )
    name = _required_text(name, "Component name")
    component_code = _optional_text(
        component_code, "Component code"
    )
    category = _optional_text(category, "Category")
    description = _optional_text(
        description, "Description", 5000
    )
    criticality = _required_choice(
        criticality,
        COMPONENT_CRITICALITY_LEVELS,
        "component criticality"
    )
    is_active = _boolean(is_active, "Active status")

    database = get_db()

    try:
        with database:
            cursor = database.execute(
                """
                INSERT INTO components (
                    name,
                    component_code,
                    category,
                    description,
                    criticality,
                    is_active
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    name,
                    component_code,
                    category,
                    description,
                    criticality,
                    is_active
                )
            )

            component_id = cursor.lastrowid

            _audit(
                acting_user_id,
                "CREATE",
                "Component",
                component_id,
                f"Created component: {name}"
            )

        return get_component_details(component_id)

    except Exception as exc:
        if "UNIQUE constraint failed" in str(exc):
            raise SupplierValidationError(
                "This component code is already in use."
            ) from exc
        raise


def get_component_details(component_id):
    component_id = _positive_id(
        component_id, "Component ID"
    )

    row = get_db().execute(
        """
        SELECT *
        FROM components
        WHERE id = ?
        """,
        (component_id,)
    ).fetchone()

    if row is None:
        raise ComponentNotFoundError(
            "Component record not found."
        )

    result = dict(row)

    result["supplier_count"] = get_db().execute(
        """
        SELECT COUNT(*)
        FROM supplier_components
        WHERE component_id = ?
        """,
        (component_id,)
    ).fetchone()[0]

    return result


def get_component_records(
    search=None,
    criticality=None,
    active_only=False
):
    conditions = []
    parameters = []

    if search:
        search = _optional_text(search, "Search", 255)
        if search:
            conditions.append(
                "(name LIKE ? OR component_code LIKE ? OR category LIKE ?)"
            )
            term = f"%{search}%"
            parameters.extend([term, term, term])

    if criticality:
        conditions.append("criticality = ?")
        parameters.append(
            _required_choice(
                criticality,
                COMPONENT_CRITICALITY_LEVELS,
                "component criticality"
            )
        )

    if active_only:
        conditions.append("is_active = 1")

    where_clause = (
        "WHERE " + " AND ".join(conditions)
        if conditions else ""
    )

    rows = get_db().execute(
        f"""
        SELECT
            components.*,
            (
                SELECT COUNT(*)
                FROM supplier_components sc
                WHERE sc.component_id = components.id
            ) AS supplier_count
        FROM components
        {where_clause}
        ORDER BY name COLLATE NOCASE
        """,
        parameters
    ).fetchall()

    return [dict(row) for row in rows]


def update_component(
    component_id,
    acting_user_id,
    updates
):
    component_id = _positive_id(
        component_id, "Component ID"
    )
    acting_user_id = _positive_id(
        acting_user_id, "Acting user ID"
    )

    allowed = {
        "name", "component_code", "category",
        "description", "criticality", "is_active"
    }

    if not isinstance(updates, dict) or not updates:
        raise SupplierValidationError(
            "No component updates were provided."
        )

    if not set(updates).issubset(allowed):
        raise SupplierValidationError(
            "One or more component fields are not editable."
        )

    cleaned = {}

    for field, value in updates.items():
        if field == "name":
            cleaned[field] = _required_text(
                value, "Component name"
            )
        elif field in {"component_code", "category"}:
            cleaned[field] = _optional_text(
                value, field.replace("_", " ").title()
            )
        elif field == "description":
            cleaned[field] = _optional_text(
                value, "Description", 5000
            )
        elif field == "criticality":
            cleaned[field] = _required_choice(
                value,
                COMPONENT_CRITICALITY_LEVELS,
                "component criticality"
            )
        elif field == "is_active":
            cleaned[field] = _boolean(
                value, "Active status"
            )

    database = get_db()

    try:
        with database:
            _get_component_or_raise(
                database, component_id
            )

            assignments = ", ".join(
                f"{field} = ?" for field in cleaned
            )

            database.execute(
                f"""
                UPDATE components
                SET {assignments},
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (*cleaned.values(), component_id)
            )

            _audit(
                acting_user_id,
                "UPDATE",
                "Component",
                component_id,
                "Updated component record."
            )

        return get_component_details(component_id)

    except Exception as exc:
        if "UNIQUE constraint failed" in str(exc):
            raise SupplierValidationError(
                "This component code is already in use."
            ) from exc
        raise


def delete_component(component_id, acting_user_id):
    component_id = _positive_id(
        component_id, "Component ID"
    )
    acting_user_id = _positive_id(
        acting_user_id, "Acting user ID"
    )

    database = get_db()

    with database:
        _get_component_or_raise(
            database, component_id
        )

        procurement_count = database.execute(
            """
            SELECT COUNT(*)
            FROM procurement_records
            WHERE component_id = ?
            """,
            (component_id,)
        ).fetchone()[0]

        if procurement_count:
            raise SupplierValidationError(
                "This component has procurement records and cannot be deleted."
            )

        database.execute(
            "DELETE FROM components WHERE id = ?",
            (component_id,)
        )

        _audit(
            acting_user_id,
            "DELETE",
            "Component",
            component_id,
            "Deleted component record."
        )

    return True


# =========================================================
# SUPPLIER-COMPONENT MAPPING
# =========================================================

def add_supplier_component(
    acting_user_id,
    supplier_id,
    component_id,
    unit_cost=None,
    lead_time_days=None,
    dependency_share_percent=None,
    is_alternative=False
):
    acting_user_id = _positive_id(
        acting_user_id, "Acting user ID"
    )
    supplier_id = _positive_id(
        supplier_id, "Supplier ID"
    )
    component_id = _positive_id(
        component_id, "Component ID"
    )

    unit_cost = _optional_number(
        unit_cost, "Unit cost", minimum=0
    )
    lead_time_days = _optional_number(
        lead_time_days,
        "Lead time",
        minimum=0,
        integer=True
    )
    dependency_share_percent = _optional_number(
        dependency_share_percent,
        "Dependency share",
        minimum=0,
        maximum=100
    )
    is_alternative = _boolean(
        is_alternative, "Alternative supplier status"
    )

    database = get_db()

    try:
        with database:
            _get_supplier_or_raise(
                database, supplier_id
            )
            _get_component_or_raise(
                database, component_id
            )

            cursor = database.execute(
                """
                INSERT INTO supplier_components (
                    supplier_id,
                    component_id,
                    unit_cost,
                    lead_time_days,
                    dependency_share_percent,
                    is_alternative
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    supplier_id,
                    component_id,
                    unit_cost,
                    lead_time_days,
                    dependency_share_percent,
                    is_alternative
                )
            )

            mapping_id = cursor.lastrowid

            _audit(
                acting_user_id,
                "CREATE",
                "SupplierComponent",
                mapping_id,
                "Linked supplier to component."
            )

        return get_supplier_component(mapping_id)

    except Exception as exc:
        if "UNIQUE constraint failed" in str(exc):
            raise SupplierComponentError(
                "This supplier is already mapped to this component."
            ) from exc
        raise


def get_supplier_component(mapping_id):
    mapping_id = _positive_id(
        mapping_id, "Mapping ID"
    )

    row = get_db().execute(
        """
        SELECT
            sc.*,
            s.name AS supplier_name,
            c.name AS component_name,
            c.component_code
        FROM supplier_components sc
        JOIN suppliers s ON s.id = sc.supplier_id
        JOIN components c ON c.id = sc.component_id
        WHERE sc.id = ?
        """,
        (mapping_id,)
    ).fetchone()

    if row is None:
        raise SupplierComponentError(
            "Supplier-component mapping not found."
        )

    return dict(row)


def get_supplier_components(supplier_id=None, component_id=None):
    database = get_db()

    conditions = []
    parameters = []

    if supplier_id is not None:
        conditions.append("sc.supplier_id = ?")
        parameters.append(
            _positive_id(supplier_id, "Supplier ID")
        )

    if component_id is not None:
        conditions.append("sc.component_id = ?")
        parameters.append(
            _positive_id(component_id, "Component ID")
        )

    where_clause = (
        "WHERE " + " AND ".join(conditions)
        if conditions else ""
    )

    rows = database.execute(
        f"""
        SELECT
            sc.*,
            s.name AS supplier_name,
            s.risk_level AS supplier_risk_level,
            c.name AS component_name,
            c.component_code,
            c.criticality AS component_criticality
        FROM supplier_components sc
        JOIN suppliers s ON s.id = sc.supplier_id
        JOIN components c ON c.id = sc.component_id
        {where_clause}
        ORDER BY c.name, s.name
        """,
        parameters
    ).fetchall()

    return [dict(row) for row in rows]


def update_supplier_component(
    mapping_id,
    acting_user_id,
    updates
):
    mapping_id = _positive_id(
        mapping_id, "Mapping ID"
    )
    acting_user_id = _positive_id(
        acting_user_id, "Acting user ID"
    )

    allowed = {
        "unit_cost",
        "lead_time_days",
        "dependency_share_percent",
        "is_alternative"
    }

    if not isinstance(updates, dict) or not updates:
        raise SupplierValidationError(
            "No mapping updates were provided."
        )

    if not set(updates).issubset(allowed):
        raise SupplierValidationError(
            "One or more mapping fields are not editable."
        )

    cleaned = {}

    for field, value in updates.items():
        if field == "unit_cost":
            cleaned[field] = _optional_number(
                value, "Unit cost", minimum=0
            )
        elif field == "lead_time_days":
            cleaned[field] = _optional_number(
                value, "Lead time",
                minimum=0, integer=True
            )
        elif field == "dependency_share_percent":
            cleaned[field] = _optional_number(
                value, "Dependency share",
                minimum=0, maximum=100
            )
        elif field == "is_alternative":
            cleaned[field] = _boolean(
                value, "Alternative supplier status"
            )

    database = get_db()

    with database:
        existing = database.execute(
            """
            SELECT id
            FROM supplier_components
            WHERE id = ?
            """,
            (mapping_id,)
        ).fetchone()

        if existing is None:
            raise SupplierComponentError(
                "Supplier-component mapping not found."
            )

        assignments = ", ".join(
            f"{field} = ?" for field in cleaned
        )

        database.execute(
            f"""
            UPDATE supplier_components
            SET {assignments}
            WHERE id = ?
            """,
            (*cleaned.values(), mapping_id)
        )

        _audit(
            acting_user_id,
            "UPDATE",
            "SupplierComponent",
            mapping_id,
            "Updated supplier-component mapping."
        )

    return get_supplier_component(mapping_id)


def remove_supplier_component(mapping_id, acting_user_id):
    mapping_id = _positive_id(
        mapping_id, "Mapping ID"
    )
    acting_user_id = _positive_id(
        acting_user_id, "Acting user ID"
    )

    database = get_db()

    with database:
        existing = database.execute(
            """
            SELECT id
            FROM supplier_components
            WHERE id = ?
            """,
            (mapping_id,)
        ).fetchone()

        if existing is None:
            raise SupplierComponentError(
                "Supplier-component mapping not found."
            )

        database.execute(
            """
            DELETE FROM supplier_components
            WHERE id = ?
            """,
            (mapping_id,)
        )

        _audit(
            acting_user_id,
            "DELETE",
            "SupplierComponent",
            mapping_id,
            "Removed supplier-component mapping."
        )

    return True


# =========================================================
# FACILITIES
# =========================================================

def create_facility(
    acting_user_id,
    supplier_id,
    facility_name,
    facility_type=None,
    country=None,
    city=None,
    capacity_description=None,
    operational_status="Active"
):
    acting_user_id = _positive_id(
        acting_user_id, "Acting user ID"
    )
    supplier_id = _positive_id(
        supplier_id, "Supplier ID"
    )
    facility_name = _required_text(
        facility_name, "Facility name"
    )
    facility_type = _optional_text(
        facility_type, "Facility type"
    )
    country = _optional_text(country, "Country")
    city = _optional_text(city, "City")
    capacity_description = _optional_text(
        capacity_description,
        "Capacity description",
        5000
    )
    operational_status = _required_choice(
        operational_status,
        FACILITY_STATUSES,
        "operational status"
    )

    database = get_db()

    with database:
        _get_supplier_or_raise(database, supplier_id)

        cursor = database.execute(
            """
            INSERT INTO facilities (
                supplier_id,
                facility_name,
                facility_type,
                country,
                city,
                capacity_description,
                operational_status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                supplier_id,
                facility_name,
                facility_type,
                country,
                city,
                capacity_description,
                operational_status
            )
        )

        facility_id = cursor.lastrowid

        _audit(
            acting_user_id,
            "CREATE",
            "SupplierFacility",
            facility_id,
            f"Created facility: {facility_name}"
        )

    return get_facility_details(facility_id)


def get_facility_details(facility_id):
    facility_id = _positive_id(
        facility_id, "Facility ID"
    )

    row = get_db().execute(
        """
        SELECT
            f.*,
            s.name AS supplier_name
        FROM facilities f
        JOIN suppliers s ON s.id = f.supplier_id
        WHERE f.id = ?
        """,
        (facility_id,)
    ).fetchone()

    if row is None:
        raise FacilityNotFoundError(
            "Facility record not found."
        )

    return dict(row)


def get_facility_records(supplier_id=None):
    query = """
        SELECT
            f.*,
            s.name AS supplier_name
        FROM facilities f
        JOIN suppliers s ON s.id = f.supplier_id
    """

    parameters = ()

    if supplier_id is not None:
        query += " WHERE f.supplier_id = ?"
        parameters = (
            _positive_id(supplier_id, "Supplier ID"),
        )

    query += " ORDER BY s.name, f.facility_name"

    rows = get_db().execute(
        query, parameters
    ).fetchall()

    return [dict(row) for row in rows]


def update_facility(
    facility_id,
    acting_user_id,
    updates
):
    facility_id = _positive_id(
        facility_id, "Facility ID"
    )
    acting_user_id = _positive_id(
        acting_user_id, "Acting user ID"
    )

    allowed = {
        "facility_name",
        "facility_type",
        "country",
        "city",
        "capacity_description",
        "operational_status"
    }

    if not isinstance(updates, dict) or not updates:
        raise SupplierValidationError(
            "No facility updates were provided."
        )

    if not set(updates).issubset(allowed):
        raise SupplierValidationError(
            "One or more facility fields are not editable."
        )

    cleaned = {}

    for field, value in updates.items():
        if field == "facility_name":
            cleaned[field] = _required_text(
                value, "Facility name"
            )
        elif field == "capacity_description":
            cleaned[field] = _optional_text(
                value, "Capacity description", 5000
            )
        elif field == "operational_status":
            cleaned[field] = _required_choice(
                value, FACILITY_STATUSES,
                "operational status"
            )
        else:
            cleaned[field] = _optional_text(
                value, field.replace("_", " ").title()
            )

    database = get_db()

    with database:
        existing = database.execute(
            "SELECT id FROM facilities WHERE id = ?",
            (facility_id,)
        ).fetchone()

        if existing is None:
            raise FacilityNotFoundError(
                "Facility record not found."
            )

        assignments = ", ".join(
            f"{field} = ?" for field in cleaned
        )

        database.execute(
            f"""
            UPDATE facilities
            SET {assignments}
            WHERE id = ?
            """,
            (*cleaned.values(), facility_id)
        )

        _audit(
            acting_user_id,
            "UPDATE",
            "SupplierFacility",
            facility_id,
            "Updated supplier facility."
        )

    return get_facility_details(facility_id)


def delete_facility(facility_id, acting_user_id):
    facility_id = _positive_id(
        facility_id, "Facility ID"
    )
    acting_user_id = _positive_id(
        acting_user_id, "Acting user ID"
    )

    database = get_db()

    with database:
        existing = database.execute(
            "SELECT id FROM facilities WHERE id = ?",
            (facility_id,)
        ).fetchone()

        if existing is None:
            raise FacilityNotFoundError(
                "Facility record not found."
            )

        database.execute(
            "DELETE FROM facilities WHERE id = ?",
            (facility_id,)
        )

        _audit(
            acting_user_id,
            "DELETE",
            "SupplierFacility",
            facility_id,
            "Deleted supplier facility."
        )

    return True


# =========================================================
# PROCUREMENT RECORDS
# =========================================================

def create_procurement_record(
    acting_user_id,
    company_id,
    supplier_id,
    component_id,
    annual_spend,
    spend_share_percent=None,
    quantity=None,
    unit_cost=None,
    contract_start_date=None,
    contract_end_date=None,
    contract_status="Active"
):
    acting_user_id = _positive_id(
        acting_user_id, "Acting user ID"
    )
    company_id = _positive_id(
        company_id, "Company ID"
    )
    supplier_id = _positive_id(
        supplier_id, "Supplier ID"
    )
    component_id = _positive_id(
        component_id, "Component ID"
    )

    annual_spend = _optional_number(
        annual_spend, "Annual spend", minimum=0
    )

    if annual_spend is None:
        raise SupplierValidationError(
            "Annual spend is required."
        )

    spend_share_percent = _optional_number(
        spend_share_percent,
        "Spend share",
        minimum=0,
        maximum=100
    )
    quantity = _optional_number(
        quantity, "Quantity", minimum=0
    )
    unit_cost = _optional_number(
        unit_cost, "Unit cost", minimum=0
    )

    contract_start_date = _optional_text(
        contract_start_date, "Contract start date", 10
    )
    contract_end_date = _optional_text(
        contract_end_date, "Contract end date", 10
    )

    from datetime import date

    try:
        if contract_start_date:
            date.fromisoformat(contract_start_date)

        if contract_end_date:
            date.fromisoformat(contract_end_date)

    except ValueError as error:
        raise SupplierValidationError(
            "Contract dates must be valid ISO dates (YYYY-MM-DD)."
        ) from error

    if (
        contract_start_date
        and contract_end_date
        and contract_start_date > contract_end_date
    ):
        raise SupplierValidationError(
            "Contract start date cannot be later than contract end date."
        )

    contract_status = _required_choice(
        contract_status,
        CONTRACT_STATUSES,
        "contract status"
    )

    database = get_db()

    with database:
        _get_supplier_or_raise(database, supplier_id)
        _get_component_or_raise(database, component_id)

        company = database.execute(
            "SELECT id FROM companies WHERE id = ?",
            (company_id,)
        ).fetchone()

        if company is None:
            raise SupplierValidationError(
                "Company record not found."
            )

        cursor = database.execute(
            """
            INSERT INTO procurement_records (
                company_id,
                supplier_id,
                component_id,
                annual_spend,
                spend_share_percent,
                quantity,
                unit_cost,
                contract_start_date,
                contract_end_date,
                contract_status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                company_id,
                supplier_id,
                component_id,
                annual_spend,
                spend_share_percent,
                quantity,
                unit_cost,
                contract_start_date,
                contract_end_date,
                contract_status
            )
        )

        record_id = cursor.lastrowid

        _audit(
            acting_user_id,
            "CREATE",
            "ProcurementRecord",
            record_id,
            "Created procurement record."
        )

    return get_procurement_record(record_id)


def get_procurement_record(record_id):
    record_id = _positive_id(
        record_id, "Procurement record ID"
    )

    row = get_db().execute(
        """
        SELECT
            pr.*,
            co.name AS company_name,
            s.name AS supplier_name,
            c.name AS component_name,
            c.criticality AS component_criticality
        FROM procurement_records pr
        JOIN companies co ON co.id = pr.company_id
        JOIN suppliers s ON s.id = pr.supplier_id
        JOIN components c ON c.id = pr.component_id
        WHERE pr.id = ?
        """,
        (record_id,)
    ).fetchone()

    if row is None:
        raise ProcurementRecordNotFoundError(
            "Procurement record not found."
        )

    return dict(row)


def get_procurement_records(
    company_id=None,
    supplier_id=None,
    component_id=None,
    contract_status=None
):
    conditions = []
    parameters = []

    if company_id is not None:
        conditions.append("pr.company_id = ?")
        parameters.append(
            _positive_id(company_id, "Company ID")
        )

    if supplier_id is not None:
        conditions.append("pr.supplier_id = ?")
        parameters.append(
            _positive_id(supplier_id, "Supplier ID")
        )

    if component_id is not None:
        conditions.append("pr.component_id = ?")
        parameters.append(
            _positive_id(component_id, "Component ID")
        )

    if contract_status:
        conditions.append("pr.contract_status = ?")
        parameters.append(
            _required_choice(
                contract_status,
                CONTRACT_STATUSES,
                "contract status"
            )
        )

    where_clause = (
        "WHERE " + " AND ".join(conditions)
        if conditions else ""
    )

    rows = get_db().execute(
        f"""
        SELECT
            pr.*,
            co.name AS company_name,
            s.name AS supplier_name,
            c.name AS component_name,
            c.criticality AS component_criticality
        FROM procurement_records pr
        JOIN companies co ON co.id = pr.company_id
        JOIN suppliers s ON s.id = pr.supplier_id
        JOIN components c ON c.id = pr.component_id
        {where_clause}
        ORDER BY pr.recorded_at DESC, pr.id DESC
        """,
        parameters
    ).fetchall()

    return [dict(row) for row in rows]

    # ---------------------------------------------------------
# UPDATE PROCUREMENT RECORD
# ---------------------------------------------------------

def update_procurement_record(record_id, acting_user_id, updates):
    record_id = _positive_id(
        record_id, "Procurement record ID"
    )
    acting_user_id = _positive_id(
        acting_user_id, "Acting user ID"
    )

    if not isinstance(updates, dict) or not updates:
        raise SupplierValidationError(
            "At least one procurement field must be provided."
        )

    allowed_fields = {
        "company_id",
        "supplier_id",
        "component_id",
        "annual_spend",
        "spend_share_percent",
        "quantity",
        "unit_cost",
        "contract_start_date",
        "contract_end_date",
        "contract_status"
    }

    unknown_fields = set(updates) - allowed_fields

    if unknown_fields:
        raise SupplierValidationError(
            "Unsupported procurement field(s): "
            + ", ".join(sorted(unknown_fields))
        )

    database = get_db()

    existing = database.execute(
        "SELECT * FROM procurement_records WHERE id = ?",
        (record_id,)
    ).fetchone()

    if existing is None:
        raise ProcurementRecordNotFoundError(
            "Procurement record not found."
        )

    cleaned = {}

    if "company_id" in updates:
        company_id = _positive_id(
            updates["company_id"], "Company ID"
        )

        company = database.execute(
            "SELECT id FROM companies WHERE id = ?",
            (company_id,)
        ).fetchone()

        if company is None:
            raise SupplierValidationError(
                "Company record not found."
            )

        cleaned["company_id"] = company_id

    if "supplier_id" in updates:
        supplier_id = _positive_id(
            updates["supplier_id"], "Supplier ID"
        )
        _get_supplier_or_raise(database, supplier_id)
        cleaned["supplier_id"] = supplier_id

    if "component_id" in updates:
        component_id = _positive_id(
            updates["component_id"], "Component ID"
        )
        _get_component_or_raise(database, component_id)
        cleaned["component_id"] = component_id

    if "annual_spend" in updates:
        annual_spend = _optional_number(
            updates["annual_spend"],
            "Annual spend",
            minimum=0
        )

        if annual_spend is None:
            raise SupplierValidationError(
                "Annual spend is required."
            )

        cleaned["annual_spend"] = annual_spend

    if "spend_share_percent" in updates:
        cleaned["spend_share_percent"] = _optional_number(
            updates["spend_share_percent"],
            "Spend share",
            minimum=0,
            maximum=100
        )

    if "quantity" in updates:
        cleaned["quantity"] = _optional_number(
            updates["quantity"],
            "Quantity",
            minimum=0
        )

    if "unit_cost" in updates:
        cleaned["unit_cost"] = _optional_number(
            updates["unit_cost"],
            "Unit cost",
            minimum=0
        )

    for field in ("contract_start_date", "contract_end_date"):
        if field in updates:
            value = _optional_text(
                updates[field], field.replace("_", " ").title(), 10
            )

            if value:
                from datetime import date

                try:
                    date.fromisoformat(value)
                except ValueError as error:
                    raise SupplierValidationError(
                        f"{field.replace('_', ' ').title()} "
                        "must be a valid ISO date (YYYY-MM-DD)."
                    ) from error

            cleaned[field] = value

    if "contract_status" in updates:
        cleaned["contract_status"] = _required_choice(
            updates["contract_status"],
            CONTRACT_STATUSES,
            "contract status"
        )

    current_start = cleaned.get(
        "contract_start_date",
        existing["contract_start_date"]
    )
    current_end = cleaned.get(
        "contract_end_date",
        existing["contract_end_date"]
    )

    if current_start and current_end and current_start > current_end:
        raise SupplierValidationError(
            "Contract start date cannot be later than contract end date."
        )

    if not cleaned:
        raise SupplierValidationError(
            "No valid procurement fields were provided."
        )

    assignments = ", ".join(
        f"{field} = ?" for field in cleaned
    )

    parameters = list(cleaned.values()) + [record_id]

    with database:
        database.execute(
            f"""
            UPDATE procurement_records
            SET {assignments}
            WHERE id = ?
            """,
            parameters
        )

        _audit(
            acting_user_id,
            "UPDATE",
            "ProcurementRecord",
            record_id,
            "Updated procurement record."
        )

    return get_procurement_record(record_id)


# ---------------------------------------------------------
# DELETE PROCUREMENT RECORD
# ---------------------------------------------------------

def delete_procurement_record(record_id, acting_user_id):
    record_id = _positive_id(
        record_id, "Procurement record ID"
    )
    acting_user_id = _positive_id(
        acting_user_id, "Acting user ID"
    )

    database = get_db()

    with database:
        existing = database.execute(
            """
            SELECT id
            FROM procurement_records
            WHERE id = ?
            """,
            (record_id,)
        ).fetchone()

        if existing is None:
            raise ProcurementRecordNotFoundError(
                "Procurement record not found."
            )

        database.execute(
            "DELETE FROM procurement_records WHERE id = ?",
            (record_id,)
        )

        _audit(
            acting_user_id,
            "DELETE",
            "ProcurementRecord",
            record_id,
            "Deleted procurement record."
        )

    return True
