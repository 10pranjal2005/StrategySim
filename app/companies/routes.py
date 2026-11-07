
from flask import (
    abort,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)

from flask_login import current_user

from app.companies import companies_bp

from app.companies.forms import (
    CompanyForm,
    IndustryForm,
)

from app.companies.services import (
    IndustryAlreadyExistsError,
    IndustryNotFoundError,
    CompanyNotFoundError,
    InvalidCompanyTypeError,
    get_industries,
    get_industry_details,
    create_industry as create_industry_record,
    update_industry,
    get_companies,
    get_company_details,
    create_company as create_company_record,
    update_company,
)

from app.utils.decorators import (
    authenticated_required,
    analyst_required,
)


# ---------------------------------------------------------
# HELPER FUNCTIONS
# ---------------------------------------------------------

def populate_industry_choices(form):
    """
    Populate the industry dropdown using existing
    industries from the database.
    """

    industries = get_industries()

    form.industry_id.choices = [
        (industry["id"], industry["name"])
        for industry in industries
    ]

    return industries


def get_positive_page_number():
    """
    Retrieve a valid positive page number.
    """

    page = request.args.get(
        "page",
        default=1,
        type=int
    )

    if page is None or page < 1:
        return 1

    return page


# ---------------------------------------------------------
# COMPANY DIRECTORY
# GET /companies/
# ---------------------------------------------------------

@companies_bp.route(
    "/",
    methods=["GET"]
)
@authenticated_required
def company_directory():

    search = request.args.get(
        "search",
        default="",
        type=str
    ).strip()

    industry_id = request.args.get(
        "industry_id",
        default=None,
        type=int
    )

    company_type = request.args.get(
        "company_type",
        default="",
        type=str
    ).strip()

    page = get_positive_page_number()

    limit = 25
    offset = (page - 1) * limit

    industries = get_industries()

    if company_type and company_type not in {
        "Target",
        "Competitor",
        "Other"
    }:
        abort(400)

    if industry_id is not None:
        if not any(
            industry["id"] == industry_id
            for industry in industries
        ):
            abort(400)

    companies = get_companies(
        search=search or None,
        industry_id=industry_id,
        company_type=company_type or None,
        limit=limit,
        offset=offset
    )

    return render_template(
        "companies/index.html",
        companies=companies,
        industries=industries,
        search=search,
        selected_industry_id=industry_id,
        selected_company_type=company_type,
        page=page,
        limit=limit
    )


# ---------------------------------------------------------
# CREATE COMPANY
# GET /companies/create
# POST /companies/create
# ---------------------------------------------------------

@companies_bp.route(
    "/create",
    methods=["GET", "POST"]
)
@analyst_required
def create_company():

    form = CompanyForm()

    industries = populate_industry_choices(form)

    if not industries:
        flash(
            "Create an industry before adding a company.",
            "warning"
        )

        return redirect(
            url_for("companies.create_industry")
        )

    if form.validate_on_submit():

        try:

            company_id = create_company_record(
                name=form.name.data,
                industry_id=form.industry_id.data,
                created_by=current_user.id,
                company_type=form.company_type.data,
                description=form.description.data,
                headquarters=form.headquarters.data,
                website=form.website.data,
                annual_revenue=form.annual_revenue.data,
                employee_count=form.employee_count.data,
                market_share=form.market_share.data,
                founded_year=form.founded_year.data,
                is_demo=form.is_demo.data
            )

            flash(
                "Company created successfully.",
                "success"
            )

            return redirect(
                url_for(
                    "companies.company_detail",
                    company_id=company_id
                )
            )

        except IndustryNotFoundError:
            flash(
                "The selected industry no longer exists.",
                "danger"
            )

        except InvalidCompanyTypeError as error:
            flash(str(error), "danger")

        except ValueError as error:
            flash(str(error), "danger")

        except Exception:
            flash(
                "An unexpected error occurred while creating the company.",
                "danger"
            )

    return render_template(
        "companies/create_company.html",
        form=form,
        industries=industries
    )


# ---------------------------------------------------------
# COMPANY DETAILS
# GET /companies/<company_id>
# ---------------------------------------------------------

@companies_bp.route(
    "/<int:company_id>",
    methods=["GET"]
)
@authenticated_required
def company_detail(company_id):

    company = get_company_details(company_id)

    if company is None:
        abort(404)

    return render_template(
        "companies/company_detail.html",
        company=company
    )


# ---------------------------------------------------------
# EDIT COMPANY
# GET /companies/<company_id>/edit
# POST /companies/<company_id>/edit
# ---------------------------------------------------------

@companies_bp.route(
    "/<int:company_id>/edit",
    methods=["GET", "POST"]
)
@analyst_required
def edit_company(company_id):

    company = get_company_details(company_id)

    if company is None:
        abort(404)

    form = CompanyForm()

    industries = populate_industry_choices(form)

    if not industries:
        flash(
            "No industries are available. Create an industry first.",
            "warning"
        )

        return redirect(
            url_for("companies.create_industry")
        )

    if form.validate_on_submit():

        try:

            update_company(
                company_id=company_id,
                name=form.name.data,
                industry_id=form.industry_id.data,
                acting_user_id=current_user.id,
                company_type=form.company_type.data,
                description=form.description.data,
                headquarters=form.headquarters.data,
                website=form.website.data,
                annual_revenue=form.annual_revenue.data,
                employee_count=form.employee_count.data,
                market_share=form.market_share.data,
                founded_year=form.founded_year.data,
                is_demo=form.is_demo.data
            )

            flash(
                "Company information updated successfully.",
                "success"
            )

            return redirect(
                url_for(
                    "companies.company_detail",
                    company_id=company_id
                )
            )

        except CompanyNotFoundError:
            abort(404)

        except IndustryNotFoundError:
            flash(
                "The selected industry does not exist.",
                "danger"
            )

        except InvalidCompanyTypeError as error:
            flash(str(error), "danger")

        except ValueError as error:
            flash(str(error), "danger")

        except Exception:
            flash(
                "An unexpected error occurred while updating the company.",
                "danger"
            )

    elif not form.is_submitted():

        form.name.data = company["name"]
        form.industry_id.data = company["industry_id"]
        form.company_type.data = company["company_type"]
        form.description.data = company["description"]
        form.headquarters.data = company["headquarters"]
        form.website.data = company["website"]
        form.annual_revenue.data = company["annual_revenue"]
        form.employee_count.data = company["employee_count"]
        form.market_share.data = company["market_share"]
        form.founded_year.data = company["founded_year"]
        form.is_demo.data = bool(company["is_demo"])

    return render_template(
        "companies/edit_company.html",
        form=form,
        company=company,
        industries=industries
    )


# ---------------------------------------------------------
# INDUSTRY DIRECTORY
# GET /companies/industries
# ---------------------------------------------------------

@companies_bp.route(
    "/industries",
    methods=["GET"]
)
@authenticated_required
def industry_directory():

    search = request.args.get(
        "search",
        default="",
        type=str
    ).strip()

    geography = request.args.get(
        "geography",
        default="",
        type=str
    ).strip()

    industries = get_industries(
        search=search or None,
        geography=geography or None
    )

    return render_template(
        "companies/industries.html",
        industries=industries,
        search=search,
        geography=geography
    )


# ---------------------------------------------------------
# CREATE INDUSTRY
# GET /companies/industries/create
# POST /companies/industries/create
# ---------------------------------------------------------

@companies_bp.route(
    "/industries/create",
    methods=["GET", "POST"]
)
@analyst_required
def create_industry():

    form = IndustryForm()

    if form.validate_on_submit():

        try:

            industry_id = create_industry_record(
                name=form.name.data,
                created_by=current_user.id,
                sector=form.sector.data,
                description=form.description.data,
                geography=form.geography.data,
                industry_type=form.industry_type.data
            )

            flash(
                "Industry created successfully.",
                "success"
            )

            return redirect(
                url_for(
                    "companies.industry_detail",
                    industry_id=industry_id
                )
            )

        except IndustryAlreadyExistsError as error:
            flash(str(error), "danger")

        except ValueError as error:
            flash(str(error), "danger")

        except Exception:
            flash(
                "An unexpected error occurred while creating the industry.",
                "danger"
            )

    return render_template(
        "companies/create_industry.html",
        form=form
    )


# ---------------------------------------------------------
# INDUSTRY DETAILS
# GET /companies/industries/<industry_id>
# ---------------------------------------------------------

@companies_bp.route(
    "/industries/<int:industry_id>",
    methods=["GET"]
)
@authenticated_required
def industry_detail(industry_id):

    industry = get_industry_details(industry_id)

    if industry is None:
        abort(404)

    companies = get_companies(
        industry_id=industry_id,
        limit=100,
        offset=0
    )

    return render_template(
        "companies/industry_detail.html",
        industry=industry,
        companies=companies
    )


# ---------------------------------------------------------
# EDIT INDUSTRY
# GET /companies/industries/<industry_id>/edit
# POST /companies/industries/<industry_id>/edit
# ---------------------------------------------------------

@companies_bp.route(
    "/industries/<int:industry_id>/edit",
    methods=["GET", "POST"]
)
@analyst_required
def edit_industry(industry_id):

    industry = get_industry_details(industry_id)

    if industry is None:
        abort(404)

    form = IndustryForm()

    if form.validate_on_submit():

        try:

            update_industry(
                industry_id=industry_id,
                name=form.name.data,
                acting_user_id=current_user.id,
                sector=form.sector.data,
                description=form.description.data,
                geography=form.geography.data,
                industry_type=form.industry_type.data
            )

            flash(
                "Industry information updated successfully.",
                "success"
            )

            return redirect(
                url_for(
                    "companies.industry_detail",
                    industry_id=industry_id
                )
            )

        except IndustryAlreadyExistsError as error:
            flash(str(error), "danger")

        except IndustryNotFoundError:
            abort(404)

        except ValueError as error:
            flash(str(error), "danger")

        except Exception:
            flash(
                "An unexpected error occurred while updating the industry.",
                "danger"
            )

    elif not form.is_submitted():

        form.name.data = industry["name"]
        form.sector.data = industry["sector"]
        form.description.data = industry["description"]
        form.geography.data = industry["geography"]
        form.industry_type.data = industry["industry_type"]

    return render_template(
        "companies/edit_industry.html",
        form=form,
        industry=industry
    )
