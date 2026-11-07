
from urllib.parse import urlsplit

from flask import (
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user

from app.competitors import competitors_bp

from app.competitors.forms import (
    CompetitorRelationshipForm,
    CompetitorRelationshipUpdateForm,
    DeleteCompetitorRelationshipForm,
)

from app.competitors.services import (
    CompetitorNotFoundError,
    TargetCompanyNotFoundError,
    CompetitorRelationshipNotFoundError,
    InvalidCompetitorDataError,
    DuplicateCompetitorRelationshipError,
    InvalidCompetitorRelationshipError,
    get_competitors,
    get_competitor_details,
    get_company_competitors,
    create_competitor_relationship,
    update_competitor_relationship,
    delete_competitor_relationship,
)

from app.companies.services import (
    get_industries,
    get_company_details,
)

from app.utils.decorators import (
    authenticated_required,
    analyst_required,
)


# =========================================================
# PAGINATION HELPER
# =========================================================

def get_positive_page_number():
    """
    Retrieve and validate the requested page number.

    Invalid, missing, zero, and negative values default to page 1.
    """

    try:
        page = int(request.args.get("page", 1))
    except (TypeError, ValueError):
        return 1

    return max(page, 1)


# =========================================================
# SAFE REDIRECT HELPER
# =========================================================

def get_safe_return_url(default_endpoint):
    """
    Safely handle return redirects.

    A referrer is accepted only when:
    - Its scheme is HTTP or HTTPS.
    - It contains a hostname.
    - Its hostname and port match the current request host.
    - It does not contain embedded username/password credentials.

    External referrers are rejected to prevent open redirects.

    If the referrer is missing or invalid, the user is redirected
    to the supplied internal Flask endpoint.
    """

    referrer = request.referrer

    if referrer:
        try:
            parsed_url = urlsplit(referrer)

            if (
                parsed_url.scheme.lower() in {"http", "https"}
                and parsed_url.netloc
                and parsed_url.netloc.lower() == request.host.lower()
                and parsed_url.username is None
                and parsed_url.password is None
            ):
                return referrer

        except ValueError:
            pass

    return url_for(default_endpoint)


# =========================================================
# COMPETITIVE STRENGTH HELPER
# =========================================================

def get_competitive_strength_value(form):
    """
    Convert the competitive-strength form value into an integer.

    An empty value is treated as None.

    Valid values are integers from 1 to 5.
    """

    value = form.competitive_strength.data

    if value is None or value == "":
        return None

    try:
        strength = int(value)
    except (TypeError, ValueError):
        raise InvalidCompetitorDataError(
            "Competitive strength must be an integer between 1 and 5."
        )

    if str(strength) != str(value).strip():
        raise InvalidCompetitorDataError(
            "Competitive strength must be an integer between 1 and 5."
        )

    if not 1 <= strength <= 5:
        raise InvalidCompetitorDataError(
            "Competitive strength must be between 1 and 5."
        )

    return strength


# =========================================================
# COMPETITOR FORM CHOICE HELPER
# =========================================================

def populate_competitor_choices(form, industry_id):
    """
    Populate the competitor dropdown with companies belonging
    to the specified industry.

    Only companies with company_type = Competitor are returned.
    """

    result = get_competitors(
        industry_id=industry_id,
        limit=500,
        offset=0,
    )

    form.competitor_id.choices = [
        (item["id"], item["name"])
        for item in result["items"]
    ]

    return result["items"]


# =========================================================
# COMPETITOR DIRECTORY
# =========================================================

@competitors_bp.route("/", methods=["GET"])
@authenticated_required
def competitor_directory():
    """
    Display the competitor directory.

    Features:
    - Competitor listing
    - Competitor-name search
    - Industry filtering
    - Pagination
    """

    search = request.args.get("search", "").strip()
    industry_id = request.args.get("industry_id", "").strip()

    page = get_positive_page_number()
    per_page = 25
    offset = (page - 1) * per_page

    selected_industry_id = None

    industries = get_industries()

    if industry_id:
        try:
            selected_industry_id = int(industry_id)

            if selected_industry_id <= 0:
                raise ValueError

        except (TypeError, ValueError):
            flash(
                "Invalid industry selection.",
                "warning",
            )

            return redirect(
                url_for("competitors.competitor_directory")
            )

    try:
        result = get_competitors(
            search=search or None,
            industry_id=selected_industry_id,
            limit=per_page,
            offset=offset,
        )

    except InvalidCompetitorDataError as error:
        flash(str(error), "danger")

        return redirect(
            url_for("competitors.competitor_directory")
        )

    total = result["total"]

    total_pages = max(
        1,
        (total + per_page - 1) // per_page,
    )

    if page > total_pages:
        return redirect(
            url_for(
                "competitors.competitor_directory",
                search=search,
                industry_id=industry_id,
                page=total_pages,
            )
        )

    return render_template(
        "competitors/index.html",
        competitors=result["items"],
        industries=industries,
        search=search,
        selected_industry_id=selected_industry_id,
        page=page,
        per_page=per_page,
        total=total,
        total_pages=total_pages,
    )


# =========================================================
# COMPETITOR PROFILE
# =========================================================

@competitors_bp.route(
    "/<int:competitor_id>",
    methods=["GET"],
)
@authenticated_required
def competitor_detail(competitor_id):
    """
    Display an individual competitor profile.

    The profile includes:
    - Company information
    - Industry information
    - Associated target-company relationships
    """

    try:
        competitor = get_competitor_details(
            competitor_id
        )

    except CompetitorNotFoundError:
        abort(404)

    except InvalidCompetitorDataError:
        abort(400)

    return render_template(
        "competitors/detail.html",
        competitor=competitor,
    )


# =========================================================
# TARGET COMPANY COMPETITOR RELATIONSHIPS
# =========================================================

@competitors_bp.route(
    "/for-company/<int:target_company_id>",
    methods=["GET"],
)
@authenticated_required
def company_competitor_relationships(target_company_id):
    """
    Display all competitors associated with a target company.

    The page includes:
    - Target company details
    - Linked competitors
    - Competitive strength
    - Relationship notes
    """

    try:
        result = get_company_competitors(
            target_company_id
        )

    except TargetCompanyNotFoundError:
        abort(404)

    except InvalidCompetitorRelationshipError:
        abort(404)

    except InvalidCompetitorDataError:
        abort(400)

    update_forms = {
        item["relationship_id"]: CompetitorRelationshipUpdateForm(
            prefix=f"update-{item['relationship_id']}"
        )
        for item in result["items"]
    }

    delete_forms = {
        item["relationship_id"]: DeleteCompetitorRelationshipForm(
            prefix=f"delete-{item['relationship_id']}"
        )
        for item in result["items"]
    }

    return render_template(
        "competitors/company_relationships.html",
        target_company=result["target_company"],
        relationships=result["items"],
        total=result["total"],
        update_forms=update_forms,
        delete_forms=delete_forms,
    )


# =========================================================
# CREATE COMPETITOR RELATIONSHIP
# =========================================================

@competitors_bp.route(
    "/relationships/create/<int:target_company_id>",
    methods=["GET", "POST"],
)
@analyst_required
def create_relationship(target_company_id):
    """
    Create a relationship between a target company
    and a competitor.

    Access:
    - Administrator
    - Analyst

    Business rules are validated by the service layer.
    """

    target_company = get_company_details(
        target_company_id
    )

    if target_company is None:
        abort(404)

    if target_company["company_type"] != "Target":
        abort(404)

    form = CompetitorRelationshipForm()

    available_competitors = populate_competitor_choices(
        form,
        target_company["industry_id"],
    )

    if not available_competitors:
        flash(
            "No competitors are available in this industry. "
            "Create a competitor company before adding a relationship.",
            "warning",
        )

        return redirect(
            url_for(
                "competitors.company_competitor_relationships",
                target_company_id=target_company_id,
            )
        )

    if form.validate_on_submit():

        try:
            competitive_strength = get_competitive_strength_value(
                form
            )

            relationship_id = create_competitor_relationship(
                target_company_id=target_company_id,
                competitor_id=form.competitor_id.data,
                acting_user_id=current_user.id,
                competitive_strength=competitive_strength,
                notes=form.notes.data,
            )

            flash(
                "Competitor relationship created successfully.",
                "success",
            )

            return redirect(
                url_for(
                    "competitors.company_competitor_relationships",
                    target_company_id=target_company_id,
                )
            )

        except DuplicateCompetitorRelationshipError as error:
            flash(str(error), "warning")

        except CompetitorNotFoundError as error:
            flash(str(error), "danger")

        except TargetCompanyNotFoundError:
            abort(404)

        except InvalidCompetitorRelationshipError as error:
            flash(str(error), "danger")

        except InvalidCompetitorDataError as error:
            flash(str(error), "danger")

        except Exception:
            current_app.logger.exception(
                "Unexpected error while creating competitor relationship."
            )

            flash(
                "An unexpected error occurred while creating "
                "the competitor relationship.",
                "danger",
            )

    return render_template(
        "competitors/relationship_form.html",
        form=form,
        target_company=target_company,
        available_competitors=available_competitors,
        page_title="Add Competitor Relationship",
    )


# =========================================================
# UPDATE COMPETITOR RELATIONSHIP
# =========================================================

@competitors_bp.route(
    "/relationships/<int:relationship_id>/update",
    methods=["POST"],
)
@analyst_required
def update_relationship(relationship_id):
    """
    Update an existing competitor relationship.

    Only the following fields can be updated:
    - Competitive strength
    - Relationship notes

    Access:
    - Administrator
    - Analyst
    """

    form = CompetitorRelationshipUpdateForm(
        prefix=f"update-{relationship_id}"
    )

    if not form.validate_on_submit():
        flash(
            "Invalid relationship update request. "
            "Please check the submitted values and try again.",
            "danger",
        )

        return redirect(
            get_safe_return_url(
                "competitors.competitor_directory"
            )
        )

    try:
        competitive_strength = get_competitive_strength_value(
            form
        )

        update_competitor_relationship(
            relationship_id=relationship_id,
            acting_user_id=current_user.id,
            competitive_strength=competitive_strength,
            notes=form.notes.data,
        )

        flash(
            "Competitor relationship updated successfully.",
            "success",
        )

    except CompetitorRelationshipNotFoundError:
        abort(404)

    except InvalidCompetitorDataError as error:
        flash(str(error), "danger")

    except Exception:
        current_app.logger.exception(
            "Unexpected error while updating competitor relationship."
        )

        flash(
            "An unexpected error occurred while updating "
            "the competitor relationship.",
            "danger",
        )

    return redirect(
        get_safe_return_url(
            "competitors.competitor_directory"
        )
    )


# =========================================================
# DELETE COMPETITOR RELATIONSHIP
# =========================================================

@competitors_bp.route(
    "/relationships/<int:relationship_id>/delete",
    methods=["POST"],
)
@analyst_required
def remove_relationship(relationship_id):
    """
    Delete an existing competitor relationship.

    Important:
    This operation removes only the relationship record.

    It does not delete:
    - The target company
    - The competitor company
    - Their associated company information

    Access:
    - Administrator
    - Analyst
    """

    form = DeleteCompetitorRelationshipForm(
        prefix=f"delete-{relationship_id}"
    )

    if not form.validate_on_submit():
        flash(
            "Invalid relationship deletion request. "
            "Please try again.",
            "danger",
        )

        return redirect(
            get_safe_return_url(
                "competitors.competitor_directory"
            )
        )

    try:
        delete_competitor_relationship(
            relationship_id=relationship_id,
            acting_user_id=current_user.id,
        )

        flash(
            "Competitor relationship removed successfully.",
            "success",
        )

    except CompetitorRelationshipNotFoundError:
        abort(404)

    except InvalidCompetitorDataError as error:
        flash(str(error), "danger")

    except Exception:
        current_app.logger.exception(
            "Unexpected error while deleting competitor relationship."
        )

        flash(
            "An unexpected error occurred while removing "
            "the competitor relationship.",
            "danger",
        )

    return redirect(
        get_safe_return_url(
            "competitors.competitor_directory"
        )
    )
