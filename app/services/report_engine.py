# app/services/report_engine.py

import json
import re
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from flask import current_app

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
    KeepTogether,
)

from app.database.connection import get_db
from app.services.audit_service import record_audit_log


REPORT_TYPES = {
    "company": "Company Intelligence Report",
    "strategic": "Strategic Analysis Report",
    "supply_chain": "Supply Chain Intelligence Report",
    "scenario": "Scenario Simulation Report",
    "decisions": "Strategic Decisions Report",
}


class ReportError(Exception):
    """Raised when a report cannot be generated."""


def _dict_rows(cursor):
    return [dict(row) for row in cursor.fetchall()]


def _fetch_one(query, parameters=()):
    return get_db().execute(query, parameters).fetchone()


def _fetch_all(query, parameters=()):
    return _dict_rows(
        get_db().execute(query, parameters)
    )


def _safe_text(value):
    if value is None or value == "":
        return "Unavailable"

    return str(value)


def _number(value, suffix=""):
    if value is None:
        return "Unavailable"

    try:
        return f"{float(value):,.2f}{suffix}"
    except (TypeError, ValueError):
        return _safe_text(value)


def _paragraph_text(value):
    text = _safe_text(value)
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\n", "<br/>")
    )


def _company(company_id):
    company = _fetch_one(
        """
        SELECT
            c.*,
            i.name AS industry_name,
            i.sector AS industry_sector,
            i.geography AS industry_geography
        FROM companies c
        LEFT JOIN industries i
            ON i.id = c.industry_id
        WHERE c.id = ?
          AND c.company_type = 'Target'
        """,
        (company_id,),
    )

    if company is None:
        raise ReportError(
            "The selected target company was not found."
        )

    return dict(company)


def _section(title, description, rows=None, columns=None):
    return {
        "title": title,
        "description": description,
        "columns": columns or [],
        "rows": rows or [],
    }


def _company_report(company):
    company_id = company["id"]

    competitors = _fetch_all(
        """
        SELECT
            c.name AS competitor_name,
            c.headquarters,
            c.founded_year,
            cr.competitive_strength,
            cr.notes
        FROM competitor_relationships cr
        JOIN companies c
            ON c.id = cr.competitor_id
        WHERE cr.company_id = ?
        ORDER BY c.name
        """,
        (company_id,),
    )

    profile_rows = [
        ["Company", _safe_text(company["name"])],
        ["Company Type", _safe_text(company["company_type"])],
        ["Industry", _safe_text(company.get("industry_name"))],
        ["Sector", _safe_text(company.get("industry_sector"))],
        ["Geography", _safe_text(company.get("industry_geography"))],
        ["Headquarters", _safe_text(company.get("headquarters"))],
        ["Website", _safe_text(company.get("website"))],
        ["Founded Year", _safe_text(company.get("founded_year"))],
        ["Annual Revenue", _number(company.get("annual_revenue"))],
        ["Employee Count", _safe_text(company.get("employee_count"))],
        ["Market Share", _number(company.get("market_share"), "%")],
        ["Description", _safe_text(company.get("description"))],
        [
            "Record Classification",
            "Illustrative demo record"
            if company.get("is_demo")
            else "Saved company record",
        ],
    ]

    competitor_rows = [
        [
            row["competitor_name"],
            _safe_text(row["headquarters"]),
            _safe_text(row["founded_year"]),
            _number(row["competitive_strength"]),
            _safe_text(row["notes"]),
        ]
        for row in competitors
    ]

    return [
        _section(
            "Company Profile",
            "Company information currently saved in StrategySim.",
            profile_rows,
            ["Field", "Saved Value"],
        ),
        _section(
            "Competitor Relationships",
            "Competitors linked to this target company.",
            competitor_rows,
            [
                "Competitor",
                "Headquarters",
                "Founded",
                "Competitive Strength",
                "Notes",
            ],
        ),
    ]


def _strategic_report(company):
    company_id = company["id"]
    sections = []

    swot_assessments = _fetch_all(
        """
        SELECT id, assessment_name, assessment_date, summary
        FROM swot_assessments
        WHERE company_id = ?
        ORDER BY assessment_date DESC, id DESC
        """,
        (company_id,),
    )

    for assessment in swot_assessments:
        factors = _fetch_all(
            """
            SELECT
                factor_type,
                factor_name,
                description,
                strategic_importance
            FROM swot_factors
            WHERE assessment_id = ?
            ORDER BY factor_type, factor_name
            """,
            (assessment["id"],),
        )

        rows = [
            [
                row["factor_type"],
                row["factor_name"],
                row["description"],
                _safe_text(row["strategic_importance"]),
            ]
            for row in factors
        ]

        sections.append(
            _section(
                f"SWOT: {assessment['assessment_name']}",
                (
                    f"Assessment date: "
                    f"{_safe_text(assessment['assessment_date'])}. "
                    f"Summary: {_safe_text(assessment['summary'])}"
                ),
                rows,
                [
                    "Factor Type",
                    "Factor",
                    "Description",
                    "Strategic Importance",
                ],
            )
        )

    five_force_assessments = _fetch_all(
        """
        SELECT *
        FROM five_forces_assessments
        WHERE company_id = ?
        ORDER BY assessment_date DESC, id DESC
        """,
        (company_id,),
    )

    force_labels = [
        ("Buyer Power", "buyer_power_score"),
        ("Supplier Power", "supplier_power_score"),
        ("Competitive Rivalry", "competitive_rivalry_score"),
        ("Threat of Substitution", "threat_of_substitution_score"),
        ("Threat of New Entrants", "threat_of_new_entrants_score"),
        ("Overall Score", "overall_score"),
    ]

    for assessment in five_force_assessments:
        rows = [
            [label, _number(assessment[field], "/5")]
            for label, field in force_labels
        ]

        indicators = _fetch_all(
            """
            SELECT
                force_name,
                indicator_name,
                score,
                weight,
                explanation
            FROM five_forces_indicators
            WHERE assessment_id = ?
            ORDER BY force_name, indicator_name
            """,
            (assessment["id"],),
        )

        sections.append(
            _section(
                f"Porter's Five Forces: {assessment['assessment_name']}",
                (
                    f"Assessment date: "
                    f"{_safe_text(assessment['assessment_date'])}. "
                    f"Summary: {_safe_text(assessment['summary'])}"
                ),
                rows,
                ["Force", "Score"],
            )
        )

        sections.append(
            _section(
                f"Five Forces Indicators: {assessment['assessment_name']}",
                "Saved indicators supporting the force assessment.",
                [
                    [
                        row["force_name"],
                        row["indicator_name"],
                        _number(row["score"], "/5"),
                        _number(row["weight"]),
                        row["explanation"],
                    ]
                    for row in indicators
                ],
                [
                    "Force",
                    "Indicator",
                    "Score",
                    "Weight",
                    "Explanation",
                ],
            )
        )

    value_chain_assessments = _fetch_all(
        """
        SELECT id, assessment_name, assessment_date, summary
        FROM value_chain_assessments
        WHERE company_id = ?
        ORDER BY assessment_date DESC, id DESC
        """,
        (company_id,),
    )

    for assessment in value_chain_assessments:
        activities = _fetch_all(
            """
            SELECT
                activity_category,
                activity_name,
                description,
                cost_contribution,
                strategic_importance,
                competitive_advantage
            FROM value_chain_activities
            WHERE assessment_id = ?
            ORDER BY activity_category, activity_name
            """,
            (assessment["id"],),
        )

        sections.append(
            _section(
                f"Value Chain: {assessment['assessment_name']}",
                (
                    f"Assessment date: "
                    f"{_safe_text(assessment['assessment_date'])}. "
                    f"Summary: {_safe_text(assessment['summary'])}"
                ),
                [
                    [
                        row["activity_category"],
                        row["activity_name"],
                        row["description"],
                        _number(row["cost_contribution"]),
                        _safe_text(row["strategic_importance"]),
                        _safe_text(row["competitive_advantage"]),
                    ]
                    for row in activities
                ],
                [
                    "Category",
                    "Activity",
                    "Description",
                    "Cost Contribution",
                    "Strategic Importance",
                    "Competitive Advantage",
                ],
            )
        )

    if not sections:
        sections.append(
            _section(
                "Strategic Analysis Records",
                "No saved SWOT, Five Forces or Value Chain assessments "
                "were found for this company.",
            )
        )

    return sections


def _supply_chain_report(company):
    company_id = company["id"]

    supplier_rows = _fetch_all(
        """
        SELECT
            s.id,
            s.name AS supplier_name,
            s.supplier_code,
            s.country,
            s.supplier_type,
            s.tier_level,
            s.risk_level,
            s.is_active,
            c.name AS component_name,
            c.component_code,
            c.criticality,
            sc.unit_cost,
            sc.lead_time_days,
            sc.dependency_share_percent,
            sc.is_alternative
        FROM supplier_components sc
        JOIN suppliers s
            ON s.id = sc.supplier_id
        JOIN components c
            ON c.id = sc.component_id
        WHERE s.is_active = 1
        ORDER BY s.name, c.name
        """
    )

    facilities = _fetch_all(
        """
        SELECT
            s.name AS supplier_name,
            f.facility_name,
            f.facility_type,
            f.country,
            f.city,
            f.capacity_description,
            f.operational_status
        FROM facilities f
        JOIN suppliers s
            ON s.id = f.supplier_id
        ORDER BY s.name, f.facility_name
        """
    )

    procurement = _fetch_all(
        """
        SELECT
            s.name AS supplier_name,
            c.name AS component_name,
            p.annual_spend,
            p.spend_share_percent,
            p.quantity,
            p.unit_cost,
            p.contract_start_date,
            p.contract_end_date,
            p.contract_status
        FROM procurement_records p
        JOIN suppliers s
            ON s.id = p.supplier_id
        JOIN components c
            ON c.id = p.component_id
        WHERE p.company_id = ?
        ORDER BY s.name, c.name
        """,
        (company_id,),
    )

    relationships = _fetch_all(
        """
        SELECT
            source.name AS source_supplier,
            target.name AS target_supplier,
            sr.relationship_type,
            sr.dependency_strength,
            sr.description
        FROM supplier_relationships sr
        JOIN suppliers source
            ON source.id = sr.source_supplier_id
        JOIN suppliers target
            ON target.id = sr.target_supplier_id
        ORDER BY source.name, target.name
        """
    )

    mapping_data = [
        [
            row["supplier_name"],
            row["supplier_code"],
            row["component_name"],
            row["criticality"],
            _number(row["unit_cost"]),
            _safe_text(row["lead_time_days"]),
            _number(row["dependency_share_percent"], "%"),
            "Alternative" if row["is_alternative"] else "Primary",
            row["risk_level"],
        ]
        for row in supplier_rows
    ]

    facility_data = [
        [
            row["supplier_name"],
            row["facility_name"],
            _safe_text(row["facility_type"]),
            _safe_text(row["city"]),
            _safe_text(row["country"]),
            _safe_text(row["operational_status"]),
            _safe_text(row["capacity_description"]),
        ]
        for row in facilities
    ]

    procurement_data = [
        [
            row["supplier_name"],
            row["component_name"],
            _number(row["annual_spend"]),
            _number(row["spend_share_percent"], "%"),
            _number(row["quantity"]),
            _number(row["unit_cost"]),
            _safe_text(row["contract_status"]),
        ]
        for row in procurement
    ]

    relationship_data = [
        [
            row["source_supplier"],
            row["target_supplier"],
            row["relationship_type"],
            _number(row["dependency_strength"], "%"),
            _safe_text(row["description"]),
        ]
        for row in relationships
    ]

    return [
        _section(
            "Supplier–Component Network",
            (
                "Active supplier-to-component mappings. "
                "Primary and alternative mappings are distinguished. "
                "Mappings are not treated as proof of actual procurement."
            ),
            mapping_data,
            [
                "Supplier",
                "Code",
                "Component",
                "Criticality",
                "Unit Cost",
                "Lead Time (days)",
                "Dependency Share",
                "Mapping Type",
                "Risk",
            ],
        ),
        _section(
            "Supplier Facilities",
            "Saved supplier facility records.",
            facility_data,
            [
                "Supplier",
                "Facility",
                "Type",
                "City",
                "Country",
                "Status",
                "Capacity",
            ],
        ),
        _section(
            "Procurement Records",
            (
                "Procurement transactions recorded for the selected "
                "target company. If no records exist, actual spend "
                "and purchase volumes cannot be established."
            ),
            procurement_data,
            [
                "Supplier",
                "Component",
                "Annual Spend",
                "Spend Share",
                "Quantity",
                "Unit Cost",
                "Contract Status",
            ],
        ),
        _section(
            "Supplier Relationships",
            "Saved links between suppliers.",
            relationship_data,
            [
                "Source Supplier",
                "Target Supplier",
                "Relationship",
                "Dependency Strength",
                "Description",
            ],
        ),
    ]


def _scenario_report(company):
    scenarios = _fetch_all(
        """
        SELECT
            id,
            scenario_name,
            scenario_type,
            description,
            parameters_json,
            baseline_metrics_json,
            status,
            created_at
        FROM scenarios
        WHERE company_id = ?
        ORDER BY created_at DESC, id DESC
        """,
        (company["id"],),
    )

    sections = []

    for scenario in scenarios:
        try:
            parameters = json.loads(
                scenario["parameters_json"] or "{}"
            )
        except (TypeError, ValueError):
            parameters = {}

        try:
            baseline = json.loads(
                scenario["baseline_metrics_json"] or "{}"
            )
        except (TypeError, ValueError):
            baseline = {}

        results = _fetch_all(
            """
            SELECT
                result_name,
                baseline_value,
                simulated_value,
                change_value,
                change_percent,
                interpretation
            FROM scenario_results
            WHERE scenario_id = ?
            ORDER BY id
            """,
            (scenario["id"],),
        )

        parameter_rows = [
            [key.replace("_", " ").title(), _safe_text(value)]
            for key, value in parameters.items()
        ]

        if not parameter_rows:
            parameter_rows = [["Parameters", "Unavailable"]]

        sections.append(
            _section(
                f"Scenario: {scenario['scenario_name']}",
                (
                    f"Type: {_safe_text(scenario['scenario_type'])}. "
                    f"Status: {_safe_text(scenario['status'])}. "
                    f"Created: {_safe_text(scenario['created_at'])}. "
                    f"Description: {_safe_text(scenario['description'])}"
                ),
                parameter_rows,
                ["Parameter", "Saved Value"],
            )
        )

        baseline_rows = [
            [key.replace("_", " ").title(), _safe_text(value)]
            for key, value in baseline.items()
        ]

        sections.append(
            _section(
                f"Baseline Metrics: {scenario['scenario_name']}",
                "Baseline values saved when the scenario was created.",
                baseline_rows,
                ["Metric", "Baseline Value"],
            )
        )

        sections.append(
            _section(
                f"Simulation Results: {scenario['scenario_name']}",
                "Calculated results saved by the scenario engine.",
                [
                    [
                        row["result_name"],
                        _number(row["baseline_value"]),
                        _number(row["simulated_value"]),
                        _number(row["change_value"]),
                        _number(row["change_percent"], "%"),
                        _safe_text(row["interpretation"]),
                    ]
                    for row in results
                ],
                [
                    "Result",
                    "Baseline",
                    "Simulated",
                    "Change",
                    "Change %",
                    "Interpretation",
                ],
            )
        )

    if not sections:
        sections.append(
            _section(
                "Scenario Records",
                "No saved scenarios were found for this company.",
            )
        )

    return sections


def _decision_report(company):
    matrices = _fetch_all(
        """
        SELECT
            id,
            matrix_name,
            objective,
            description,
            created_at
        FROM decision_matrices
        WHERE company_id = ?
        ORDER BY created_at DESC, id DESC
        """,
        (company["id"],),
    )

    sections = []

    for matrix in matrices:
        criteria = _fetch_all(
            """
            SELECT id, criterion_name, weight, description
            FROM decision_criteria
            WHERE matrix_id = ?
            ORDER BY id
            """,
            (matrix["id"],),
        )

        options = _fetch_all(
            """
            SELECT id, option_name, description
            FROM decision_options
            WHERE matrix_id = ?
            ORDER BY id
            """,
            (matrix["id"],),
        )

        sections.append(
            _section(
                f"Decision Matrix: {matrix['matrix_name']}",
                (
                    f"Objective: {_safe_text(matrix['objective'])}. "
                    f"Description: {_safe_text(matrix['description'])}. "
                    f"Created: {_safe_text(matrix['created_at'])}"
                ),
                [
                    [
                        row["criterion_name"],
                        _number(row["weight"]),
                        _safe_text(row["description"]),
                    ]
                    for row in criteria
                ],
                ["Criterion", "Weight", "Description"],
            )
        )

        sections.append(
            _section(
                f"Alternatives: {matrix['matrix_name']}",
                "Options saved in this decision matrix.",
                [
                    [row["option_name"], _safe_text(row["description"])]
                    for row in options
                ],
                ["Alternative", "Description"],
            )
        )

        total_weight = sum(
            float(row["weight"] or 0)
            for row in criteria
        )

        rankings = []

        for option in options:
            scores = _fetch_all(
                """
                SELECT
                    dc.criterion_name,
                    dc.weight,
                    ds.score,
                    ds.justification
                FROM decision_scores ds
                JOIN decision_criteria dc
                    ON dc.id = ds.criterion_id
                WHERE ds.option_id = ?
                  AND dc.matrix_id = ?
                ORDER BY dc.id
                """,
                (option["id"], matrix["id"]),
            )

            complete = (
                len(scores) == len(criteria)
                and len(criteria) > 0
                and total_weight > 0
            )

            if complete:
                weighted_total = sum(
                    float(score["score"]) * float(score["weight"])
                    for score in scores
                )
                weighted_average = weighted_total / total_weight
                status = "Evaluated"
            else:
                weighted_average = None
                status = "Pending Evaluation"

            rankings.append({
                "name": option["option_name"],
                "score": weighted_average,
                "status": status,
                "scores": scores,
            })

        evaluated = [
            item for item in rankings
            if item["score"] is not None
        ]

        evaluated.sort(
            key=lambda item: item["score"],
            reverse=True,
        )

        previous_score = None
        current_rank = 0

        for index, item in enumerate(evaluated, start=1):
            if item["score"] != previous_score:
                current_rank = index

            item["rank"] = current_rank
            previous_score = item["score"]

        ranking_rows = [
            [
                item["rank"],
                item["name"],
                f"{item['score']:.3f}/5",
                item["status"],
            ]
            for item in evaluated
        ]

        ranking_rows.extend(
            [
                ["—", item["name"], "—", item["status"]]
                for item in rankings
                if item["score"] is None
            ]
        )

        sections.append(
            _section(
                f"Decision Rankings: {matrix['matrix_name']}",
                (
                    "Weighted average = sum(score × criterion weight) "
                    "divided by total criterion weight. Only alternatives "
                    "with complete evaluations are ranked."
                ),
                ranking_rows,
                ["Rank", "Alternative", "Weighted Score", "Status"],
            )
        )

        for option in options:
            score_rows = _fetch_all(
                """
                SELECT
                    dc.criterion_name,
                    dc.weight,
                    ds.score,
                    ds.weighted_score,
                    ds.justification
                FROM decision_scores ds
                JOIN decision_criteria dc
                    ON dc.id = ds.criterion_id
                WHERE ds.option_id = ?
                  AND dc.matrix_id = ?
                ORDER BY dc.id
                """,
                (option["id"], matrix["id"]),
            )

            sections.append(
                _section(
                    f"Evaluation: {option['option_name']}",
                    "Saved criterion-level evaluations and justifications.",
                    [
                        [
                            row["criterion_name"],
                            _number(row["weight"]),
                            _number(row["score"], "/5"),
                            _number(row["weighted_score"]),
                            _safe_text(row["justification"]),
                        ]
                        for row in score_rows
                    ],
                    [
                        "Criterion",
                        "Weight",
                        "Score",
                        "Weighted Score",
                        "Justification",
                    ],
                )
            )

    if not sections:
        sections.append(
            _section(
                "Decision Records",
                "No saved decision matrices were found for this company.",
            )
        )

    return sections


def build_report_data(report_type, company_id):
    """Collects saved records for one supported report category."""

    if report_type not in REPORT_TYPES:
        raise ReportError("Invalid report category selected.")

    company = _company(company_id)

    builders = {
        "company": _company_report,
        "strategic": _strategic_report,
        "supply_chain": _supply_chain_report,
        "scenario": _scenario_report,
        "decisions": _decision_report,
    }

    return {
        "report_type": report_type,
        "title": REPORT_TYPES[report_type],
        "company": company,
        "generated_at": datetime.now().strftime("%d %B %Y, %I:%M %p"),
        "sections": builders[report_type](company),
    }


def _pdf_styles():
    styles = getSampleStyleSheet()

    styles.add(
        ParagraphStyle(
            name="ReportTitleCustom",
            parent=styles["Title"],
            fontName="Helvetica-Bold",
            fontSize=19,
            leading=24,
            textColor=colors.HexColor("#172554"),
            alignment=TA_CENTER,
            spaceAfter=8,
        )
    )

    styles.add(
        ParagraphStyle(
            name="ReportSubtitleCustom",
            parent=styles["Normal"],
            fontSize=10,
            leading=14,
            textColor=colors.HexColor("#475569"),
            alignment=TA_CENTER,
        )
    )

    styles.add(
        ParagraphStyle(
            name="ReportSectionCustom",
            parent=styles["Heading2"],
            fontSize=12,
            leading=16,
            textColor=colors.HexColor("#1E3A8A"),
            spaceBefore=12,
            spaceAfter=6,
        )
    )

    styles.add(
        ParagraphStyle(
            name="ReportBodyCustom",
            parent=styles["BodyText"],
            fontSize=8,
            leading=11,
        )
    )

    styles.add(
        ParagraphStyle(
            name="ReportCellCustom",
            parent=styles["BodyText"],
            fontSize=7,
            leading=9,
            wordWrap="CJK",
        )
    )

    return styles


def _make_table(section, styles):
    columns = section["columns"]
    rows = section["rows"]

    if not columns:
        return Paragraph(
            _paragraph_text(section["description"]),
            styles["ReportBodyCustom"],
        )

    table_data = [
        [
            Paragraph(_paragraph_text(value), styles["ReportCellCustom"])
            for value in columns
        ]
    ]

    for row in rows:
        table_data.append(
            [
                Paragraph(_paragraph_text(value), styles["ReportCellCustom"])
                for value in row
            ]
        )

    if len(table_data) == 1:
        table_data.append([
            Paragraph(
                "No saved records available.",
                styles["ReportCellCustom"],
            )
        ] + [
            Paragraph("", styles["ReportCellCustom"])
            for _ in range(max(0, len(columns) - 1))
        ])

    page_width = landscape(A4)[0] - 30 * mm
    column_width = page_width / len(columns)

    table = Table(
        table_data,
        colWidths=[column_width] * len(columns),
        repeatRows=1,
        hAlign="LEFT",
    )

    table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E2E8F0")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#0F172A")),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#CBD5E1")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [
                colors.white,
                colors.HexColor("#F8FAFC"),
            ]),
        ])
    )

    return table


def _draw_page(canvas, document):
    canvas.saveState()

    width, _ = landscape(A4)

    canvas.setStrokeColor(colors.HexColor("#CBD5E1"))
    canvas.line(
        15 * mm,
        13 * mm,
        width - 15 * mm,
        13 * mm,
    )

    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(colors.HexColor("#64748B"))

    canvas.drawString(
        15 * mm,
        8 * mm,
        "StrategySim | Strategic Intelligence",
    )

    canvas.drawRightString(
        width - 15 * mm,
        8 * mm,
        f"Page {document.page}",
    )

    canvas.restoreState()


def _build_pdf(report_data, output_path):
    styles = _pdf_styles()

    document = SimpleDocTemplate(
        str(output_path),
        pagesize=landscape(A4),
        rightMargin=15 * mm,
        leftMargin=15 * mm,
        topMargin=17 * mm,
        bottomMargin=19 * mm,
        title=report_data["title"],
        author="StrategySim",
    )

    company = report_data["company"]

    story = [
        Spacer(1, 12 * mm),
        Paragraph(
            "StrategySim",
            styles["ReportTitleCustom"],
        ),
        Paragraph(
            _paragraph_text(report_data["title"]),
            styles["ReportSubtitleCustom"],
        ),
        Spacer(1, 8 * mm),
        Paragraph(
            f"<b>Company:</b> {_paragraph_text(company['name'])}",
            styles["ReportBodyCustom"],
        ),
        Paragraph(
            f"<b>Generated:</b> {_paragraph_text(report_data['generated_at'])}",
            styles["ReportBodyCustom"],
        ),
        Paragraph(
            "<b>Data basis:</b> Saved application records available "
            "at the time this report was generated.",
            styles["ReportBodyCustom"],
        ),
        Spacer(1, 7 * mm),
    ]

    for section in report_data["sections"]:
        section_content = [
            Paragraph(
                _paragraph_text(section["title"]),
                styles["ReportSectionCustom"],
            ),
            Paragraph(
                _paragraph_text(section["description"]),
                styles["ReportBodyCustom"],
            ),
            Spacer(1, 3 * mm),
            _make_table(section, styles),
            Spacer(1, 5 * mm),
        ]

        story.append(KeepTogether(section_content))

    document.build(
        story,
        onFirstPage=_draw_page,
        onLaterPages=_draw_page,
    )


def generate_report(report_type, company_id, user_id):
    """
    Generates a PDF report and records the activity in audit_logs.

    Returns metadata containing the generated filename and report data.
    """

    report_data = build_report_data(
        report_type,
        company_id,
    )

    reports_directory = (
        Path(current_app.instance_path) / "reports"
    )

    reports_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    token = uuid4().hex[:8]

    safe_company = re.sub(
        r"[^A-Za-z0-9_-]+",
        "_",
        report_data["company"]["name"],
    ).strip("_")[:40]

    filename = (
        f"{report_type}_{safe_company}_{timestamp}_{token}.pdf"
    )

    output_path = reports_directory / filename

    try:
        _build_pdf(report_data, output_path)

        record_audit_log(
            user_id=user_id,
            action="report_generated",
            entity_type="report",
            entity_id=company_id,
            description=(
                f"Generated {REPORT_TYPES[report_type]} "
                f"for {report_data['company']['name']}. "
                f"File: {filename}"
            ),
        )

    except Exception:
        if output_path.exists():
            output_path.unlink()
        raise

    return {
        "filename": filename,
        "title": report_data["title"],
        "company_name": report_data["company"]["name"],
        "generated_at": report_data["generated_at"],
        "sections": report_data["sections"],
        "path": str(output_path),
    }


def get_report_history(limit=50):
    """Returns generated report entries from the existing audit log."""

    rows = _fetch_all(
        """
        SELECT
            al.id,
            al.user_id,
            al.entity_id,
            al.description,
            al.created_at,
            u.full_name
        FROM audit_logs al
        LEFT JOIN users u
            ON u.id = al.user_id
        WHERE al.action = 'report_generated'
          AND al.entity_type = 'report'
        ORDER BY al.id DESC
        LIMIT ?
        """,
        (limit,),
    )

    reports_directory = (
        Path(current_app.instance_path) / "reports"
    )

    history = []

    for row in rows:
        match = re.search(
            r"File:\s*([A-Za-z0-9_.-]+\.pdf)",
            row["description"] or "",
        )

        filename = match.group(1) if match else None

        if filename:
            file_path = reports_directory / filename
            available = file_path.is_file()
        else:
            available = False

        history.append({
            "id": row["id"],
            "filename": filename,
            "description": row["description"],
            "generated_at": row["created_at"],
            "generated_by": row["full_name"] or "Unavailable",
            "available": available,
        })

    return history


def get_report_file_path(filename):
    """Validates a report filename and returns its existing PDF path."""

    if (
        not filename
        or Path(filename).name != filename
        or not filename.endswith(".pdf")
        or not re.fullmatch(r"[A-Za-z0-9_.-]+\.pdf", filename)
    ):
        raise ReportError("Invalid report filename.")

    reports_directory = (
        Path(current_app.instance_path) / "reports"
    )

    file_path = reports_directory / filename

    if not file_path.is_file():
        raise ReportError("The requested report file was not found.")

    return file_path