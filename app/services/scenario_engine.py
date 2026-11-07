
"""
Scenario Simulation Engine
StrategySim — Decision Support

Uses the existing scenarios and scenario_results tables.
No database migration is required.
"""

import json
from datetime import datetime

from app.database.connection import get_db, execute_transaction
from app.services.audit_service import record_audit_log


# =========================================================
# CONSTANTS
# =========================================================

SCENARIO_TYPES = {
    "supplier_price_increase": "Supplier Price Increase",
    "supplier_unavailability": "Supplier Unavailability",
    "raw_material_shortage": "Raw Material Shortage",
    "demand_decline": "Demand Decline",
    "competitor_entry": "Competitor Entry",
    "substitute_technology": "Substitute Technology",
}

SCENARIO_STATUSES = ("Draft", "Simulated", "Archived")

MAX_PERCENTAGE = 100


# =========================================================
# EXCEPTIONS
# =========================================================

class ScenarioError(Exception):
    """Base exception for Scenario Simulator."""


class ScenarioNotFoundError(ScenarioError):
    """Raised when a scenario does not exist."""


class ScenarioValidationError(ScenarioError):
    """Raised when scenario input is invalid."""


class ScenarioDataError(ScenarioError):
    """Raised when required source data is unavailable."""


# =========================================================
# VALIDATION HELPERS
# =========================================================

def _positive_id(value, field_name="ID"):
    try:
        value = int(value)
    except (TypeError, ValueError):
        raise ScenarioValidationError(
            f"{field_name} must be a valid integer."
        )

    if value <= 0:
        raise ScenarioValidationError(
            f"{field_name} must be greater than zero."
        )

    return value


def _percentage(value, field_name):
    try:
        value = float(value)
    except (TypeError, ValueError):
        raise ScenarioValidationError(
            f"{field_name} must be a number."
        )

    if not 0 <= value <= MAX_PERCENTAGE:
        raise ScenarioValidationError(
            f"{field_name} must be between 0 and 100."
        )

    return value


def _required_text(value, field_name, maximum=150):
    if not isinstance(value, str) or not value.strip():
        raise ScenarioValidationError(
            f"{field_name} is required."
        )

    value = value.strip()

    if len(value) > maximum:
        raise ScenarioValidationError(
            f"{field_name} cannot exceed {maximum} characters."
        )

    return value


def _json_dump(data):
    return json.dumps(data, allow_nan=False)


def _json_load(value, default=None):
    if not value:
        return default if default is not None else {}

    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return default if default is not None else {}


# =========================================================
# COMPANY AND BASELINE DATA
# =========================================================

def get_company_baseline(company_id):
    """
    Calculate baseline metrics for a selected company.

    Only actual database values are used.
    Missing financial or procurement data is represented
    as unavailable rather than estimated.
    """

    company_id = _positive_id(company_id, "Company ID")
    database = get_db()

    company = database.execute(
        """
        SELECT
            id,
            name,
            company_type,
            annual_revenue,
            market_share,
            employee_count,
            is_demo
        FROM companies
        WHERE id = ?
        """,
        (company_id,)
    ).fetchone()

    if not company:
        raise ScenarioDataError(
            "The selected company does not exist."
        )

    procurement = database.execute(
        """
        SELECT
            COUNT(*) AS record_count,
            SUM(annual_spend) AS annual_spend,
            AVG(unit_cost) AS average_unit_cost,
            SUM(quantity) AS total_quantity
        FROM procurement_records
        WHERE company_id = ?
          AND contract_status = 'Active'
        """,
        (company_id,)
    ).fetchone()

    supplier_count = database.execute(
        """
        SELECT COUNT(DISTINCT supplier_id) AS total
        FROM procurement_records
        WHERE company_id = ?
          AND contract_status = 'Active'
        """,
        (company_id,)
    ).fetchone()["total"]

    return {
        "company_id": company["id"],
        "company_name": company["name"],
        "company_type": company["company_type"],
        "annual_revenue": company["annual_revenue"],
        "market_share": company["market_share"],
        "employee_count": company["employee_count"],
        "is_demo": bool(company["is_demo"]),
        "procurement_record_count": procurement["record_count"],
        "annual_procurement_spend": procurement["annual_spend"],
        "average_procurement_unit_cost": procurement["average_unit_cost"],
        "total_procurement_quantity": procurement["total_quantity"],
        "active_procurement_supplier_count": supplier_count,
    }


# =========================================================
# SCENARIO PARAMETER VALIDATION
# =========================================================

def validate_scenario_parameters(scenario_type, parameters):
    if scenario_type not in SCENARIO_TYPES:
        raise ScenarioValidationError(
            "Invalid scenario type."
        )

    if not isinstance(parameters, dict):
        raise ScenarioValidationError(
            "Scenario parameters must be provided as a dictionary."
        )

    validated = {}

    # -----------------------------------------------------
    # PERCENTAGE PARAMETER VALIDATION
    # -----------------------------------------------------

    percentage_fields = {
        "supplier_price_increase": "price_increase_percent",
        "raw_material_shortage": "shortage_percent",
        "demand_decline": "demand_decline_percent",
        "competitor_entry": "market_share_impact_percent",
        "substitute_technology": "demand_impact_percent",
    }

    if scenario_type in percentage_fields:
        field = percentage_fields[scenario_type]

        if field not in parameters:
            raise ScenarioValidationError(
                f"{field} is required."
            )

        validated[field] = _percentage(
            parameters[field],
            field.replace("_", " ").title()
        )

    # -----------------------------------------------------
    # SUPPLIER ID VALIDATION
    # -----------------------------------------------------

    if scenario_type in (
        "supplier_price_increase",
        "supplier_unavailability",
    ):
        if parameters.get("supplier_id") is not None:
            validated["supplier_id"] = _positive_id(
                parameters["supplier_id"],
                "Supplier ID"
            )

    if scenario_type in (
        "supplier_price_increase",
        "supplier_unavailability",
    ):
        if not validated.get("supplier_id"):
            raise ScenarioValidationError(
                "A supplier must be selected."
            )

    # -----------------------------------------------------
    # COMPONENT ID VALIDATION
    # -----------------------------------------------------

    if scenario_type in (
        "raw_material_shortage",
        "supplier_price_increase",
        "supplier_unavailability",
    ):
        if parameters.get("component_id") is not None:
            validated["component_id"] = _positive_id(
                parameters["component_id"],
                "Component ID"
            )

    if scenario_type in (
        "raw_material_shortage",
        "supplier_price_increase",
    ):
        if not validated.get("component_id"):
            raise ScenarioValidationError(
                "A component must be selected."
            )

    return validated

# =========================================================
# SCENARIO CREATION
# =========================================================

def create_scenario(
    company_id,
    scenario_name,
    scenario_type,
    parameters,
    created_by,
    description=None
):
    """
    Create a new scenario in Draft status.
    """

    company_id = _positive_id(company_id, "Company ID")
    created_by = _positive_id(created_by, "User ID")

    scenario_name = _required_text(
        scenario_name,
        "Scenario name"
    )

    if scenario_type not in SCENARIO_TYPES:
        raise ScenarioValidationError(
            "Invalid scenario type."
        )

    parameters = validate_scenario_parameters(
        scenario_type,
        parameters
    )

    if description is not None:
        if not isinstance(description, str):
            raise ScenarioValidationError(
                "Description must be text."
            )

        description = description.strip()

        if len(description) > 2000:
            raise ScenarioValidationError(
                "Description cannot exceed 2000 characters."
            )

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
                raise ScenarioDataError(
                    "Selected company was not found."
                )

        if company["company_type"] != "Target":
                raise ScenarioValidationError(
                    "Scenarios must be evaluated against the target company. "
                    "Competitor companies cannot be selected as the target."
                )

        user = database.execute(
            "SELECT id FROM users WHERE id = ? AND is_active = 1",
            (created_by,)
        ).fetchone()

        if not user:
            raise ScenarioValidationError(
                "Active creator account was not found."
            )

        cursor = database.execute(
            """
            INSERT INTO scenarios (
                company_id,
                scenario_name,
                scenario_type,
                description,
                parameters_json,
                status,
                created_by
            )
            VALUES (?, ?, ?, ?, ?, 'Draft', ?)
            """,
            (
                company_id,
                scenario_name,
                scenario_type,
                description,
                _json_dump(parameters),
                created_by,
            )
        )

        scenario_id = cursor.lastrowid

        record_audit_log(
            user_id=created_by,
            action="CREATE",
            entity_type="Scenario",
            entity_id=scenario_id,
            description=f"Created scenario: {scenario_name}",
            commit=False
        )

        return scenario_id

    return execute_transaction(operation)


# =========================================================
# SCENARIO RETRIEVAL
# =========================================================

def get_scenario(scenario_id):
    scenario_id = _positive_id(scenario_id, "Scenario ID")
    database = get_db()

    row = database.execute(
        """
        SELECT
            s.*,
            c.name AS company_name,
            u.full_name AS creator_name
        FROM scenarios s
        JOIN companies c ON c.id = s.company_id
        LEFT JOIN users u ON u.id = s.created_by
        WHERE s.id = ?
        """,
        (scenario_id,)
    ).fetchone()

    if not row:
        raise ScenarioNotFoundError(
            "Scenario not found."
        )

    scenario = dict(row)
    scenario["parameters"] = _json_load(
        scenario.pop("parameters_json")
    )
    scenario["baseline_metrics"] = _json_load(
        scenario.pop("baseline_metrics_json")
    )

    return scenario


def get_scenarios(company_id=None, status=None):
    """
    Return scenarios, optionally filtered by company and status.
    """

    database = get_db()

    query = """
        SELECT
            s.id,
            s.company_id,
            s.scenario_name,
            s.scenario_type,
            s.description,
            s.status,
            s.created_at,
            s.updated_at,
            c.name AS company_name,
            u.full_name AS creator_name
        FROM scenarios s
        JOIN companies c ON c.id = s.company_id
        LEFT JOIN users u ON u.id = s.created_by
        WHERE 1 = 1
    """

    values = []

    if company_id is not None:
        query += " AND s.company_id = ?"
        values.append(
            _positive_id(company_id, "Company ID")
        )

    if status is not None:
        if status not in SCENARIO_STATUSES:
            raise ScenarioValidationError(
                "Invalid scenario status."
            )

        query += " AND s.status = ?"
        values.append(status)

    query += " ORDER BY s.created_at DESC, s.id DESC"

    return [
        dict(row)
        for row in database.execute(query, values).fetchall()
    ]


def get_scenario_results(scenario_id):
    scenario_id = _positive_id(scenario_id, "Scenario ID")
    database = get_db()

    scenario = database.execute(
        "SELECT id FROM scenarios WHERE id = ?",
        (scenario_id,)
    ).fetchone()

    if not scenario:
        raise ScenarioNotFoundError(
            "Scenario not found."
        )

    rows = database.execute(
        """
        SELECT *
        FROM scenario_results
        WHERE scenario_id = ?
        ORDER BY id
        """,
        (scenario_id,)
    ).fetchall()

    results = []

    for row in rows:
        result = dict(row)
        result["result_data"] = _json_load(
            result.pop("result_data_json")
        )
        results.append(result)

    return results


# =========================================================
# RESULT CALCULATION HELPERS
# =========================================================

def _result(
    name,
    baseline,
    simulated,
    interpretation,
    unit=None,
    availability="Available"
):
    if baseline is None or simulated is None:
        change = None
        change_percent = None
    else:
        change = simulated - baseline
        change_percent = (
            (change / baseline) * 100
            if baseline != 0 else None
        )

    return {
        "result_name": name,
        "baseline_value": baseline,
        "simulated_value": simulated,
        "change_value": change,
        "change_percent": change_percent,
        "interpretation": interpretation,
        "result_data": {
            "unit": unit,
            "availability": availability,
        }
    }


def _revenue_impact(baseline, reduction_percent, label):
    if baseline is None:
        return _result(
            "Annual Revenue",
            None,
            None,
            "Revenue data is unavailable.",
            "Currency",
            "Unavailable"
        )

    simulated = baseline * (
        1 - reduction_percent / 100
    )

    return _result(
        "Annual Revenue",
        baseline,
        simulated,
        f"{label}: {reduction_percent:.2f}% assumed reduction.",
        "Currency"
    )


def _get_supplier(supplier_id):
    database = get_db()

    supplier = database.execute(
        """
        SELECT id, name, risk_level, is_active
        FROM suppliers
        WHERE id = ?
        """,
        (supplier_id,)
    ).fetchone()

    if not supplier:
        raise ScenarioValidationError(
            "Selected supplier was not found."
        )

    return dict(supplier)


def _get_component(component_id):
    database = get_db()

    component = database.execute(
        """
        SELECT id, name, criticality, is_active
        FROM components
        WHERE id = ?
        """,
        (component_id,)
    ).fetchone()

    if not component:
        raise ScenarioValidationError(
            "Selected component was not found."
        )

    return dict(component)


# =========================================================
# SCENARIO SIMULATION
# =========================================================

def simulate_scenario(scenario_id, executed_by):
    """
    Execute a scenario and store its results.

    Each execution replaces the previous result rows for
    that scenario, preserving the scenario itself.
    """

    scenario_id = _positive_id(scenario_id, "Scenario ID")
    executed_by = _positive_id(executed_by, "User ID")

    def operation(database):
        scenario = database.execute(
            """
            SELECT *
            FROM scenarios
            WHERE id = ?
            """,
            (scenario_id,)
        ).fetchone()

        if not scenario:
            raise ScenarioNotFoundError(
                "Scenario not found."
            )

        if scenario["status"] == "Archived":
            raise ScenarioValidationError(
                "Archived scenarios cannot be simulated."
            )

        parameters = _json_load(
            scenario["parameters_json"]
        )

        scenario_type = scenario["scenario_type"]

        baseline = get_company_baseline(
            scenario["company_id"]
        )

        results = []
        assumptions = []

        # -------------------------------------------------
        # 1. SUPPLIER PRICE INCREASE
        # -------------------------------------------------

        if scenario_type == "supplier_price_increase":

            supplier_id = parameters["supplier_id"]
            component_id = parameters["component_id"]
            increase = parameters["price_increase_percent"]

            supplier = _get_supplier(supplier_id)
            component = _get_component(component_id)

            mapping = database.execute(
                """
                SELECT
                    sc.unit_cost,
                    sc.lead_time_days,
                    sc.dependency_share_percent,
                    sc.is_alternative,
                    s.name AS supplier_name,
                    c.name AS component_name
                FROM supplier_components sc
                JOIN suppliers s ON s.id = sc.supplier_id
                JOIN components c ON c.id = sc.component_id
                WHERE sc.supplier_id = ?
                  AND sc.component_id = ?
                  AND s.is_active = 1
                  AND c.is_active = 1
                """,
                (supplier_id, component_id)
            ).fetchone()

            if mapping and mapping["unit_cost"] is not None:
                unit_cost = float(mapping["unit_cost"])
                simulated_unit_cost = unit_cost * (
                    1 + increase / 100
                )

                supplier_classification = (
                    "Alternative supplier"
                    if mapping["is_alternative"]
                    else "Primary supplier"
                )

                results.append(
                    _result(
                        "Mapped Supplier Unit Cost",
                        unit_cost,
                        simulated_unit_cost,
                        (
                            f"{supplier_classification}. "
                            f"Mapped unit cost increases by "
                            f"{increase:.2f}%. "
                            "This is a mapping-based unit-cost "
                            "scenario, not confirmed purchase expenditure."
                        ),
                        "Currency"
                    )
                )

                assumptions.append(
                    f"Supplier: {supplier['name']}."
                )
                assumptions.append(
                    f"Component: {component['name']}."
                )
                assumptions.append(
                    f"Supplier classification: {supplier_classification}."
                )
            else:
                results.append(
                    _result(
                        "Mapped Supplier Unit Cost",
                        None,
                        None,
                        (
                            "No usable unit cost exists for the selected "
                            "supplier-component mapping."
                        ),
                        "Currency",
                        "Unavailable"
                    )
                )

            procurement = database.execute(
                """
                SELECT
                    COUNT(*) AS record_count,
                    SUM(annual_spend) AS annual_spend
                FROM procurement_records
                WHERE company_id = ?
                  AND supplier_id = ?
                  AND component_id = ?
                  AND contract_status = 'Active'
                """,
                (
                    scenario["company_id"],
                    supplier_id,
                    component_id,
                )
            ).fetchone()

            if (
                procurement["record_count"] > 0
                and procurement["annual_spend"] is not None
            ):
                spend = float(procurement["annual_spend"])
                simulated_spend = spend * (
                    1 + increase / 100
                )

                results.append(
                    _result(
                        "Annual Procurement Cost",
                        spend,
                        simulated_spend,
                        (
                            "Calculated using recorded active "
                            "procurement expenditure."
                        ),
                        "Currency"
                    )
                )
            else:
                results.append(
                    _result(
                        "Annual Procurement Cost",
                        None,
                        None,
                        (
                            "No matching active procurement records "
                            "exist for this company, supplier and "
                            "component. Annual financial impact "
                            "cannot be calculated."
                        ),
                        "Currency",
                        "Unavailable"
                    )
                )

            assumptions.append(
                f"Supplier price increase assumption: {increase:.2f}%."
            )
            assumptions.append(
                "Unit-cost impact uses the recorded supplier-component "
                "mapping. It does not establish actual purchase volume."
            )

        # -------------------------------------------------
        # 2. SUPPLIER UNAVAILABILITY
        # -------------------------------------------------

        elif scenario_type == "supplier_unavailability":

            supplier_id = parameters["supplier_id"]
            supplier = _get_supplier(supplier_id)

            component_id = parameters.get("component_id")

            if component_id:
                _get_component(component_id)

            exposure = database.execute(
                """
                SELECT
                    COUNT(*) AS record_count,
                    SUM(annual_spend) AS annual_spend
                FROM procurement_records
                WHERE company_id = ?
                  AND supplier_id = ?
                  AND contract_status = 'Active'
                  AND (? IS NULL OR component_id = ?)
                """,
                (
                    scenario["company_id"],
                    supplier_id,
                    component_id,
                    component_id,
                )
            ).fetchone()

            results.append(
                _result(
                    "Supplier Operational Availability",
                    100.0,
                    0.0,
                    f"Supplier {supplier['name']} is assumed unavailable.",
                    "Percent"
                )
            )

            if exposure["record_count"] and exposure["annual_spend"] is not None:
                results.append(
                    _result(
                        "Affected Annual Procurement Spend",
                        exposure["annual_spend"],
                        0.0,
                        "Recorded procurement exposure associated with this supplier.",
                        "Currency"
                    )
                )
            else:
                results.append(
                    _result(
                        "Affected Annual Procurement Spend",
                        None,
                        None,
                        "No matching active company procurement records exist.",
                        "Currency",
                        "Unavailable"
                    )
                )

            assumptions.append(
                "Supplier unavailability is a scenario assumption, not a confirmed real-world disruption."
            )

        # -------------------------------------------------
        # 3. RAW MATERIAL SHORTAGE
        # -------------------------------------------------

        elif scenario_type == "raw_material_shortage":

            component_id = parameters["component_id"]
            component = _get_component(component_id)
            shortage = parameters["shortage_percent"]

            mappings = database.execute(
                """
                SELECT
                    sc.id,
                    sc.supplier_id,
                    sc.is_alternative,
                    sc.dependency_share_percent,
                    s.name AS supplier_name
                FROM supplier_components sc
                JOIN suppliers s ON s.id = sc.supplier_id
                WHERE sc.component_id = ?
                  AND s.is_active = 1
                """,
                (component_id,)
            ).fetchall()

            procurement = database.execute(
                """
                SELECT
                    COUNT(*) AS record_count,
                    SUM(annual_spend) AS annual_spend
                FROM procurement_records
                WHERE company_id = ?
                  AND component_id = ?
                  AND contract_status = 'Active'
                """,
                (
                    scenario["company_id"],
                    component_id,
                )
            ).fetchone()

            results.append(
                _result(
                    "Component Availability",
                    100.0,
                    100.0 - shortage,
                    f"Assumed component availability reduction of {shortage:.2f}%.",
                    "Percent"
                )
            )

            results.append(
                _result(
                    "Mapped Active Suppliers",
                    float(len(mappings)),
                    float(len(mappings)),
                    "Existing supplier-component mappings. This does not establish actual production capacity.",
                    "Count"
                )
            )

            if procurement["record_count"] and procurement["annual_spend"] is not None:
                affected = procurement["annual_spend"] * shortage / 100

                results.append(
                    _result(
                        "Illustrative Procurement Exposure",
                        procurement["annual_spend"],
                        affected,
                        "Value of procurement spend corresponding to the assumed shortage percentage; not a confirmed financial loss.",
                        "Currency"
                    )
                )
            else:
                results.append(
                    _result(
                        "Procurement Exposure",
                        None,
                        None,
                        "Company-specific procurement data is unavailable.",
                        "Currency",
                        "Unavailable"
                    )
                )

            assumptions.append(
                f"Component: {component['name']}. Assumed shortage: {shortage:.2f}%."
            )

            assumptions.append(
                "Supplier mappings do not prove that alternative suppliers can replace unavailable capacity."
            )

        # -------------------------------------------------
        # 4. DEMAND DECLINE
        # -------------------------------------------------

        elif scenario_type == "demand_decline":

            decline = parameters["demand_decline_percent"]

            results.append(
                _revenue_impact(
                    baseline["annual_revenue"],
                    decline,
                    "Demand decline"
                )
            )

            market_share = baseline["market_share"]

            if market_share is not None:
                simulated_share = market_share * (
                    1 - decline / 100
                )

                results.append(
                    _result(
                        "Market Share",
                        market_share,
                        simulated_share,
                        "Illustrative proportional market-share reduction based on the demand-decline assumption.",
                        "Percent"
                    )
                )
            else:
                results.append(
                    _result(
                        "Market Share",
                        None,
                        None,
                        "Company market-share data is unavailable.",
                        "Percent",
                        "Unavailable"
                    )
                )

            assumptions.append(
                f"Demand is assumed to decline by {decline:.2f}%."
            )

        # -------------------------------------------------
        # 5. COMPETITOR ENTRY
        # -------------------------------------------------

        elif scenario_type == "competitor_entry":

            impact = parameters["market_share_impact_percent"]
            market_share = baseline["market_share"]

            if market_share is not None:
                simulated_share = market_share * (
                    1 - impact / 100
                )

                results.append(
                    _result(
                        "Company Market Share",
                        market_share,
                        simulated_share,
                        "Illustrative market-share reduction caused by assumed competitive pressure.",
                        "Percent"
                    )
                )
            else:
                results.append(
                    _result(
                        "Company Market Share",
                        None,
                        None,
                        "Company market-share data is unavailable.",
                        "Percent",
                        "Unavailable"
                    )
                )

            results.append(
                _result(
                    "Assumed Competitive Pressure",
                    0.0,
                    impact,
                    "User-defined competitive impact assumption; not an observed market measurement.",
                    "Percent"
                )
            )

            assumptions.append(
                f"Competitor entry is assumed to reduce the selected company's market share proportionally by {impact:.2f}%."
            )

            assumptions.append(
                "No actual entrant market share or competitor financial data is automatically inferred."
            )

        # -------------------------------------------------
        # 6. SUBSTITUTE TECHNOLOGY
        # -------------------------------------------------

        elif scenario_type == "substitute_technology":

            impact = parameters["demand_impact_percent"]

            results.append(
                _revenue_impact(
                    baseline["annual_revenue"],
                    impact,
                    "Substitute technology impact"
                )
            )

            market_share = baseline["market_share"]

            if market_share is not None:
                results.append(
                    _result(
                        "Market Share",
                        market_share,
                        market_share * (1 - impact / 100),
                        "Illustrative proportional market-share reduction.",
                        "Percent"
                    )
                )

            assumptions.append(
                f"Substitute technology is assumed to reduce demand by {impact:.2f}%."
            )

            assumptions.append(
                "Technology adoption and market penetration are not independently forecast."
            )

        else:
            raise ScenarioValidationError(
                "Unsupported scenario type."
            )

        # -------------------------------------------------
        # STORE SIMULATION RESULTS
        # -------------------------------------------------

        database.execute(
            "DELETE FROM scenario_results WHERE scenario_id = ?",
            (scenario_id,)
        )

        for result in results:
            database.execute(
                """
                INSERT INTO scenario_results (
                    scenario_id,
                    result_name,
                    baseline_value,
                    simulated_value,
                    change_value,
                    change_percent,
                    interpretation,
                    result_data_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    scenario_id,
                    result["result_name"],
                    result["baseline_value"],
                    result["simulated_value"],
                    result["change_value"],
                    result["change_percent"],
                    result["interpretation"],
                    _json_dump(result["result_data"]),
                )
            )

        baseline_snapshot = {
            "company": baseline,
            "scenario_assumptions": assumptions,
            "simulated_at": datetime.utcnow().isoformat(),
            "calculation_basis": "Recorded data and explicitly supplied assumptions",
        }

        database.execute(
            """
            UPDATE scenarios
            SET
                baseline_metrics_json = ?,
                status = 'Simulated',
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                _json_dump(baseline_snapshot),
                scenario_id,
            )
        )

        record_audit_log(
            user_id=executed_by,
            action="SIMULATE",
            entity_type="Scenario",
            entity_id=scenario_id,
            description=f"Executed scenario: {scenario['scenario_name']}",
            commit=False
        )

        return {
            "scenario_id": scenario_id,
            "scenario_name": scenario["scenario_name"],
            "scenario_type": scenario_type,
            "company_name": baseline["company_name"],
            "status": "Simulated",
            "baseline": baseline,
            "assumptions": assumptions,
            "results": results,
        }

    return execute_transaction(operation)


# =========================================================
# ARCHIVE SCENARIO
# =========================================================

def archive_scenario(scenario_id, archived_by):
    scenario_id = _positive_id(scenario_id, "Scenario ID")
    archived_by = _positive_id(archived_by, "User ID")

    def operation(database):
        scenario = database.execute(
            """
            SELECT id, scenario_name, status
            FROM scenarios
            WHERE id = ?
            """,
            (scenario_id,)
        ).fetchone()

        if not scenario:
            raise ScenarioNotFoundError(
                "Scenario not found."
            )

        if scenario["status"] == "Archived":
            raise ScenarioValidationError(
                "Scenario is already archived."
            )

        database.execute(
            """
            UPDATE scenarios
            SET status = 'Archived',
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (scenario_id,)
        )

        record_audit_log(
            user_id=archived_by,
            action="ARCHIVE",
            entity_type="Scenario",
            entity_id=scenario_id,
            description=f"Archived scenario: {scenario['scenario_name']}",
            commit=False
        )

        return True

    return execute_transaction(operation)
