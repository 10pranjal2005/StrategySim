from pathlib import Path

from flask import (
    abort,
    flash,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)

from flask_login import current_user, login_required

from app.database.connection import get_db
from app.reports import reports_bp
from app.services.report_engine import (
    REPORT_TYPES,
    ReportError,
    generate_report,
    get_report_file_path,
    get_report_history,
)
from app.utils.decorators import roles_required


def _get_target_companies():
    rows = get_db().execute(
        """
        SELECT id, name
        FROM companies
        WHERE company_type = 'Target'
        ORDER BY name
        """
    ).fetchall()

    return [dict(row) for row in rows]


@reports_bp.route("/", methods=["GET"])
@login_required
def index():
    companies = _get_target_companies()

    history = get_report_history()

    return render_template(
        "reports/index.html",
        companies=companies,
        report_types=REPORT_TYPES,
        history=history,
    )


@reports_bp.route("/generate", methods=["POST"])
@roles_required("Administrator", "Analyst")
def generate():
    report_type = request.form.get("report_type", "").strip()
    company_id = request.form.get("company_id", "").strip()

    if report_type not in REPORT_TYPES:
        flash("Please select a valid report category.", "danger")
        return redirect(url_for("reports.index"))

    try:
        company_id = int(company_id)
    except (TypeError, ValueError):
        flash("Please select a valid target company.", "danger")
        return redirect(url_for("reports.index"))

    try:
        result = generate_report(
            report_type=report_type,
            company_id=company_id,
            user_id=current_user.id,
        )

        flash(
            "Your PDF report has been generated successfully.",
            "success",
        )

        return render_template(
            "reports/preview.html",
            report=result,
        )

    except ReportError as exc:
        flash(str(exc), "danger")

    except Exception:
        current_app_error = (
            "The report could not be generated. "
            "Check the application console for details."
        )
        flash(current_app_error, "danger")

    return redirect(url_for("reports.index"))


@reports_bp.route("/download/<filename>", methods=["GET"])
@login_required
def download(filename):
    try:
        file_path = get_report_file_path(filename)

    except ReportError:
        abort(404)

    return send_file(
        file_path,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=Path(file_path).name,
    )


@reports_bp.route("/history", methods=["GET"])
@login_required
def history():
    return render_template(
        "reports/history.html",
        reports=get_report_history(limit=100),
    )