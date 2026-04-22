"""
Deterministic eligibility service.

Filters visa routes based on:
- User's work authorisation status (needs sponsorship vs. no constraint)
- Salary thresholds
- Basic eligibility logic

This is DETERMINISTIC — no LLM involved. Results are right-or-wrong,
and must be computed from data, not hallucinated.
"""

from typing import Any

from app.schemas.plan import VisaRouteAssessment, PlanWarning


def assess_visa_routes(
    routes_data: list[dict[str, Any]],
    work_auth_status: str,
    salary_expectation: float,
) -> tuple[list[VisaRouteAssessment], list[PlanWarning]]:
    """
    Assess each visa route for the user's profile.

    Args:
        routes_data: Raw visa route dicts from the data layer.
        work_auth_status: 'needs_sponsorship' or 'no_constraint'.
        salary_expectation: User's expected salary in local currency.

    Returns:
        Tuple of (assessed routes, warnings).
    """
    assessments: list[VisaRouteAssessment] = []
    warnings: list[PlanWarning] = []

    for route in routes_data:
        is_eligible = True
        reasons: list[str] = []

        # --- Check sponsorship requirement ---
        sponsorship_required = route.get("sponsorship_required", False)

        if work_auth_status == "no_constraint":
            # User doesn't need sponsorship — eligible for all routes
            reasons.append("No work authorisation constraint — eligible.")
        elif work_auth_status == "needs_sponsorship":
            if sponsorship_required:
                reasons.append(
                    "This route supports employer sponsorship — eligible."
                )
            else:
                # Route doesn't offer sponsorship but user needs it
                # Still might be eligible (e.g., Job Seeker visa, Global Talent)
                route_type = route.get("type", "")
                if route_type in ("job_seeker_visa", "talent_visa"):
                    reasons.append(
                        f"This {route_type.replace('_', ' ')} does not require "
                        f"employer sponsorship — you can apply independently."
                    )
                else:
                    reasons.append(
                        "This route does not provide employer sponsorship."
                    )

        # --- Check salary threshold ---
        salary_threshold = route.get("salary_threshold")
        meets_salary = None

        if salary_threshold is not None:
            meets_salary = salary_expectation >= salary_threshold

            if not meets_salary:
                shortfall = salary_threshold - salary_expectation
                is_eligible = False
                reasons.append(
                    f"Your salary expectation of {salary_expectation:,.0f} is "
                    f"{shortfall:,.0f} below the minimum threshold of "
                    f"{salary_threshold:,.0f}. You are NOT eligible at this salary."
                )
                warnings.append(
                    PlanWarning(
                        category="salary_shortfall",
                        severity="critical",
                        message=(
                            f"Your salary expectation of {salary_expectation:,.0f} "
                            f"is {shortfall:,.0f} below the {route['name']} "
                            f"minimum threshold of {salary_threshold:,.0f}. "
                            f"You will NOT be eligible for this route at this salary."
                        ),
                    )
                )
            else:
                reasons.append(
                    f"Your salary of {salary_expectation:,.0f} meets the "
                    f"threshold of {salary_threshold:,.0f}."
                )

        assessments.append(
            VisaRouteAssessment(
                name=route["name"],
                type=route["type"],
                is_eligible=is_eligible,
                sponsorship_required=sponsorship_required,
                processing_time_months=route["processing_time_months"],
                salary_threshold=salary_threshold,
                meets_salary_threshold=meets_salary,
                eligibility_criteria=route.get("eligibility_criteria", []),
                reasons=reasons,
                data_confidence=route.get("data_confidence", "unknown"),
            )
        )

    return assessments, warnings
