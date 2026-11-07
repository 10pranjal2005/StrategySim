"""Analytical services for Supply Chain Dependency Analysis."""

from collections import defaultdict

from app.database import get_db


class DependencyAnalysisError(Exception):
    """Base exception for dependency analysis."""


class DependencyComponentNotFoundError(DependencyAnalysisError):
    """Raised when a component does not exist."""


class DependencyAnalysisValidationError(DependencyAnalysisError):
    """Raised when an invalid component ID is supplied."""


def _positive_id(value, field_name="Component ID"):
    """Validate a positive integer identifier."""

    try:
        value = int(value)
    except (TypeError, ValueError):
        raise DependencyAnalysisValidationError(
            f"{field_name} must be a valid integer."
        )

    if value <= 0:
        raise DependencyAnalysisValidationError(
            f"{field_name} must be greater than zero."
        )

    return value


def _dict_rows(rows):
    """Convert SQLite rows into dictionaries."""

    return [dict(row) for row in rows]


def _get_component_supplier_data(database, component_id=None):
    """Retrieve component and supplier mapping information."""

    query = """
        SELECT
            c.id AS component_id,
            c.name AS component_name,
            c.component_code,
            c.category,
            c.criticality,
            c.is_active AS component_is_active,

            sc.id AS mapping_id,
            sc.supplier_id,
            sc.unit_cost,
            sc.lead_time_days,
            sc.dependency_share_percent,
            sc.is_alternative,

            s.name AS supplier_name,
            s.supplier_code,
            s.country AS supplier_country,
            s.risk_level AS supplier_risk_level,
            s.is_active AS supplier_is_active

        FROM components AS c

        LEFT JOIN supplier_components AS sc
            ON sc.component_id = c.id

        LEFT JOIN suppliers AS s
            ON s.id = sc.supplier_id
    """

    parameters = ()

    if component_id is not None:
        query += " WHERE c.id = ?"
        parameters = (component_id,)

    query += """
        ORDER BY
            c.name,
            sc.is_alternative,
            s.name
    """

    return database.execute(query, parameters).fetchall()


def _get_procurement_data(database, component_id=None):
    """Retrieve procurement information."""

    query = """
        SELECT
            pr.id,
            pr.company_id,
            pr.supplier_id,
            pr.component_id,
            pr.annual_spend,
            pr.spend_share_percent,
            pr.quantity,
            pr.unit_cost,
            pr.contract_start_date,
            pr.contract_end_date,
            pr.contract_status,

            s.name AS supplier_name,
            c.name AS component_name

        FROM procurement_records AS pr

        JOIN suppliers AS s
            ON s.id = pr.supplier_id

        JOIN components AS c
            ON c.id = pr.component_id
    """

    parameters = ()

    if component_id is not None:
        query += " WHERE pr.component_id = ?"
        parameters = (component_id,)

    query += " ORDER BY pr.annual_spend DESC"

    return _dict_rows(
        database.execute(query, parameters).fetchall()
    )


def _get_facility_data(database):
    """Retrieve supplier facility operational information."""

    rows = database.execute(
        """
        SELECT
            f.id,
            f.supplier_id,
            f.facility_name,
            f.facility_type,
            f.country,
            f.city,
            f.operational_status,
            s.name AS supplier_name,
            s.risk_level AS supplier_risk_level

        FROM facilities AS f

        JOIN suppliers AS s
            ON s.id = f.supplier_id

        ORDER BY s.name, f.facility_name
        """
    ).fetchall()

    return _dict_rows(rows)


def _analyse_component(rows, procurement_records):
    """Calculate dependency indicators for one component."""

    first = rows[0]

    mappings = [
        row for row in rows
        if row["mapping_id"] is not None
    ]

    primary_suppliers = [
        row for row in mappings
        if not row["is_alternative"]
    ]

    alternative_suppliers = [
        row for row in mappings
        if row["is_alternative"]
    ]

    recorded_shares = [
        float(row["dependency_share_percent"])
        for row in primary_suppliers
        if row["dependency_share_percent"] is not None
    ]

    missing_share_count = (
        len(primary_suppliers) - len(recorded_shares)
    )

    total_recorded_share = (
        sum(recorded_shares)
        if recorded_shares else None
    )

    maximum_recorded_share = (
        max(recorded_shares)
        if recorded_shares else None
    )

    lead_times = [
        int(row["lead_time_days"])
        for row in mappings
        if row["lead_time_days"] is not None
    ]

    supplier_risk_levels = [
        row["supplier_risk_level"]
        for row in primary_suppliers
        if row["supplier_risk_level"]
    ]

    supplier_names = [
        row["supplier_name"]
        for row in primary_suppliers
    ]

    procurement = procurement_records.get(
        first["component_id"], []
    )

    annual_spend = sum(
        float(record["annual_spend"] or 0)
        for record in procurement
    )

    procurement_available = bool(procurement)

    if not mappings:
        dependency_status = "No Supplier Mapping"

    elif (
        len(primary_suppliers) == 1
        and not alternative_suppliers
    ):
        dependency_status = "Single Source"

    elif (
        len(primary_suppliers) == 1
        and alternative_suppliers
    ):
        dependency_status = "Single Primary Supplier"

    else:
        dependency_status = "Multiple Suppliers"

    if maximum_recorded_share is None:
        concentration_status = "Insufficient Data"
    elif maximum_recorded_share >= 75:
        concentration_status = "High Concentration"
    elif maximum_recorded_share >= 50:
        concentration_status = "Moderate Concentration"
    else:
        concentration_status = "Lower Recorded Concentration"

    return {
        "component_id": first["component_id"],
        "component_name": first["component_name"],
        "component_code": first["component_code"],
        "category": first["category"],
        "criticality": first["criticality"],
        "is_active": first["component_is_active"],

        "supplier_count": len(mappings),
        "primary_supplier_count": len(primary_suppliers),
        "alternative_supplier_count": len(alternative_suppliers),

        "primary_supplier_names": supplier_names,

        "dependency_status": dependency_status,
        "concentration_status": concentration_status,

        "recorded_dependency_share_percent": total_recorded_share,
        "maximum_dependency_share_percent": maximum_recorded_share,
        "missing_dependency_share_count": missing_share_count,

        "average_lead_time_days": (
            round(sum(lead_times) / len(lead_times), 2)
            if lead_times else None
        ),

        "maximum_lead_time_days": (
            max(lead_times) if lead_times else None
        ),

        "supplier_risk_levels": supplier_risk_levels,

        "procurement_record_count": len(procurement),
        "annual_spend": annual_spend if procurement_available else None,
        "procurement_available": procurement_available,
    }


def get_dependency_dashboard():
    """
    Return the complete Dependency Analysis dashboard.

    All calculations use existing supplier, component,
    mapping, procurement and facility records.
    """

    database = get_db()

    component_rows = _get_component_supplier_data(database)

    procurement_rows = _get_procurement_data(database)

    facility_rows = _get_facility_data(database)

    procurement_by_component = defaultdict(list)

    for record in procurement_rows:
        procurement_by_component[
            record["component_id"]
        ].append(record)

    component_groups = {}

    for row in component_rows:
        component_id = row["component_id"]

        component_groups.setdefault(
            component_id, []
        ).append(row)

    components = [
        _analyse_component(
            rows,
            procurement_by_component
        )
        for rows in component_groups.values()
    ]

    total_components = len(components)

    mapped_components = sum(
        1 for component in components
        if component["supplier_count"] > 0
    )

    unmapped_components = (
        total_components - mapped_components
    )

    single_source_components = sum(
        1 for component in components
        if component["dependency_status"] in [
            "Single Source",
            "Single Primary Supplier",
        ]
    )

    high_criticality_components = sum(
        1 for component in components
        if component["criticality"] in ["High", "Critical"]
    )

    components_without_alternatives = sum(
        1 for component in components
        if (
            component["supplier_count"] > 0
            and component["alternative_supplier_count"] == 0
        )
    )

    procurement_available = bool(procurement_rows)

    total_annual_spend = (
        sum(
            float(record["annual_spend"] or 0)
            for record in procurement_rows
        )
        if procurement_available else None
    )

    supplier_spend = defaultdict(float)

    for record in procurement_rows:
        supplier_spend[record["supplier_id"]] += float(
            record["annual_spend"] or 0
        )

    supplier_spend_records = []

    if procurement_available:
        for supplier_id, spend in supplier_spend.items():
            supplier_spend_records.append({
                "supplier_id": supplier_id,
                "supplier_name": next(
                    (
                        record["supplier_name"]
                        for record in procurement_rows
                        if record["supplier_id"] == supplier_id
                    ),
                    "Unknown Supplier"
                ),
                "annual_spend": spend,
                "spend_share_percent": (
                    round(
                        spend / total_annual_spend * 100,
                        2
                    )
                    if total_annual_spend else None
                ),
            })

    supplier_spend_records.sort(
        key=lambda item: item["annual_spend"],
        reverse=True
    )

    disrupted_facilities = [
        facility for facility in facility_rows
        if facility["operational_status"] == "Disrupted"
    ]

    active_facilities = [
        facility for facility in facility_rows
        if facility["operational_status"] == "Active"
    ]

    return {
        "summary": {
            "total_components": total_components,
            "mapped_components": mapped_components,
            "unmapped_components": unmapped_components,
            "single_source_components": single_source_components,
            "components_without_alternatives": (
                components_without_alternatives
            ),
            "high_criticality_components": (
                high_criticality_components
            ),
            "total_procurement_records": len(procurement_rows),
            "total_annual_spend": total_annual_spend,
            "procurement_available": procurement_available,
            "total_facilities": len(facility_rows),
            "active_facilities": len(active_facilities),
            "disrupted_facilities": len(disrupted_facilities),
        },

        "components": components,

        "supplier_spend": supplier_spend_records,

        "procurement_records": procurement_rows,

        "facilities": facility_rows,

        "disrupted_facility_records": disrupted_facilities,
    }


def get_component_dependency_details(component_id):
    """
    Return detailed dependency information for one component.
    """

    component_id = _positive_id(component_id)

    database = get_db()

    component_rows = _get_component_supplier_data(
        database,
        component_id=component_id
    )

    if not component_rows:
        raise DependencyComponentNotFoundError(
            "The requested component was not found."
        )

    procurement_records = _get_procurement_data(
        database,
        component_id=component_id
    )

    procurement_by_component = {
        component_id: procurement_records
    }

    component = _analyse_component(
        component_rows,
        procurement_by_component
    )

    suppliers = []

    for row in component_rows:
        if row["mapping_id"] is None:
            continue

        suppliers.append({
            "mapping_id": row["mapping_id"],
            "supplier_id": row["supplier_id"],
            "supplier_name": row["supplier_name"],
            "supplier_code": row["supplier_code"],
            "country": row["supplier_country"],
            "risk_level": row["supplier_risk_level"],
            "is_active": row["supplier_is_active"],
            "is_alternative": bool(row["is_alternative"]),
            "unit_cost": row["unit_cost"],
            "lead_time_days": row["lead_time_days"],
            "dependency_share_percent": (
                row["dependency_share_percent"]
            ),
        })

    facilities = _get_facility_data(database)

    supplier_ids = {
        supplier["supplier_id"]
        for supplier in suppliers
    }

    related_facilities = [
        facility for facility in facilities
        if facility["supplier_id"] in supplier_ids
    ]

    total_annual_spend = (
        sum(
            float(record["annual_spend"] or 0)
            for record in procurement_records
        )
        if procurement_records else None
    )

    return {
        "component": component,
        "suppliers": suppliers,
        "procurement_records": procurement_records,
        "total_annual_spend": total_annual_spend,
        "procurement_available": bool(procurement_records),
        "facilities": related_facilities,
    }