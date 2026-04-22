"""
Plan engine — orchestrates deterministic analysis to produce a relocation plan.

This is the core brain of the application. It:
1. Loads data for the destination/role combination
2. Runs eligibility checks (deterministic)
3. Runs salary analysis (deterministic)
4. Runs timeline analysis (deterministic)
5. Generates ranked action steps (deterministic)
6. Aggregates data confidence
7. Returns a structured PlanResult

The LLM narrative layer (Stage 4) is added ON TOP of this — it never
overrides any deterministic result.
"""

import logging
from typing import Any

from app.data_loader import (
    load_destination_role_data,
    get_data_confidence_summary,
)
from app.services.eligibility import assess_visa_routes
from app.services.salary import analyse_salary
from app.services.timeline import analyse_timeline
from app.schemas.plan import (
    PlanRequest,
    PlanResult,
    PlanWarning,
    ActionStep,
    DataConfidenceSummary,
    LlmMetadata,
)
from app.services.llm_service import generate_narrative

logger = logging.getLogger(__name__)


def generate_plan(request: PlanRequest) -> PlanResult:
    """
    Generate a complete relocation plan from user input.

    This function performs all deterministic checks and returns
    a structured plan. No LLM is called here.

    Args:
        request: The user's plan generation request.

    Returns:
        PlanResult with full analysis.

    Raises:
        DataNotFoundError: If the destination/role combination is not available.
    """
    # ----- Step 1: Load destination/role data -----
    data = load_destination_role_data(request.destination, request.target_role)

    salary_data = data["salary"]
    routes_data = data["work_authorisation"]["routes"]
    timeline_data = data["timeline"]
    credentials_data = data["credentials"]
    market_data = data["market_demand"]

    all_warnings: list[PlanWarning] = []

    # ----- Step 2: Visa route eligibility (DETERMINISTIC) -----
    visa_assessments, eligibility_warnings = assess_visa_routes(
        routes_data=routes_data,
        work_auth_status=request.work_authorisation_status,
        salary_expectation=request.salary_expectation,
    )
    all_warnings.extend(eligibility_warnings)

    # ----- Step 3: Salary analysis (DETERMINISTIC) -----
    salary_analysis = analyse_salary(
        salary_data=salary_data,
        salary_expectation=request.salary_expectation,
        visa_routes=routes_data,
    )
    # Note: salary threshold warnings are already captured via eligibility_warnings
    # above. We don't add salary_analysis.threshold_warnings to all_warnings to
    # avoid near-duplicate messages. The salary_analysis object still carries them
    # for the response payload.

    # ----- Step 4: Timeline analysis (DETERMINISTIC) -----
    # Pass eligible route data for route-specific timeline checks
    eligible_route_dicts = [
        route for route, assessment in zip(routes_data, visa_assessments)
        if assessment.is_eligible
    ]
    timeline_analysis = analyse_timeline(
        timeline_data=timeline_data,
        user_timeline_months=request.timeline_months,
        eligible_routes=eligible_route_dicts,
    )
    all_warnings.extend(timeline_analysis.warnings)

    # ----- Step 5: Generate ranked action steps (DETERMINISTIC) -----
    action_steps = _generate_action_steps(
        request=request,
        data=data,
        visa_assessments=visa_assessments,
        timeline_analysis=timeline_analysis,
        salary_analysis=salary_analysis,
    )

    # ----- Step 6: Aggregate data confidence -----
    confidence_raw = get_data_confidence_summary(data)
    data_confidence = DataConfidenceSummary(**confidence_raw)

    # ----- Step 7: Calculate overall feasibility -----
    feasibility = _calculate_feasibility(
        visa_assessments=visa_assessments,
        timeline_analysis=timeline_analysis,
        salary_analysis=salary_analysis,
        all_warnings=all_warnings,
    )

    # Deduplicate warnings (salary shortfall may appear in both eligibility and salary)
    unique_warnings = _deduplicate_warnings(all_warnings)

    # Build the deterministic plan first
    plan = PlanResult(
        destination=data["destination"],
        destination_display=data.get("destination_display", data["destination"]),
        role=data["role"],
        role_display=data.get("role_display", data["role"]),
        feasibility_score=feasibility,
        salary_analysis=salary_analysis,
        timeline_analysis=timeline_analysis,
        visa_routes=visa_assessments,
        action_steps=action_steps,
        warnings=unique_warnings,
        data_confidence=data_confidence,
        market_demand_level=market_data["level"],
        narrative=None,
        llm_metadata=None,
    )

    # ----- Step 8: LLM narrative (OPTIONAL — graceful degradation) -----
    try:
        narrative, llm_meta = generate_narrative(plan, request)
        plan.narrative = narrative
        plan.llm_metadata = LlmMetadata(**llm_meta)
    except Exception as e:
        logger.error(f"LLM integration failed: {e}")
        plan.llm_metadata = LlmMetadata(
            fallback_used=True,
            error=f"Integration error: {str(e)}",
        )

    return plan


def _calculate_feasibility(
    visa_assessments: list,
    timeline_analysis,
    salary_analysis,
    all_warnings: list[PlanWarning],
) -> str:
    """
    Calculate an overall feasibility score based on deterministic results.

    Returns: 'high' | 'medium' | 'low' | 'not_feasible'
    """
    critical_count = sum(1 for w in all_warnings if w.severity == "critical")
    eligible_routes = sum(1 for v in visa_assessments if v.is_eligible)

    if eligible_routes == 0:
        return "not_feasible"
    if critical_count >= 2:
        return "not_feasible"
    if critical_count == 1:
        return "low"
    if not timeline_analysis.is_feasible:
        return "low"
    if not salary_analysis.is_within_market_range:
        return "medium"

    # No critical warnings, timeline feasible, salary in range
    warning_count = sum(1 for w in all_warnings if w.severity == "warning")
    if warning_count > 0:
        return "medium"

    return "high"


def _deduplicate_warnings(warnings: list[PlanWarning]) -> list[PlanWarning]:
    """Remove duplicate warnings based on message content."""
    seen: set[str] = set()
    unique: list[PlanWarning] = []
    for w in warnings:
        if w.message not in seen:
            seen.add(w.message)
            unique.append(w)
    return unique


def _generate_action_steps(
    request: PlanRequest,
    data: dict[str, Any],
    visa_assessments: list,
    timeline_analysis,
    salary_analysis,
) -> list[ActionStep]:
    """
    Generate a ranked list of action steps based on the analysis.

    Order is deterministic and prioritised by urgency.
    """
    steps: list[ActionStep] = []
    order = 1

    credentials = data.get("credentials", {})
    eligible_routes = [v for v in visa_assessments if v.is_eligible]

    # --- Step: Credential preparation ---
    qualifications = credentials.get("required_qualifications", [])
    if qualifications:
        steps.append(ActionStep(
            order=order,
            title="Verify and prepare credential documentation",
            description=(
                f"Ensure your qualifications meet requirements: "
                f"{'; '.join(qualifications)}. "
                f"{credentials.get('degree_equivalency_notes', '')}"
            ),
            category="credentials",
            estimated_duration="1-2 weeks",
        ))
        order += 1

    # --- Step: Language preparation ---
    lang_reqs = credentials.get("language_requirements", [])
    if lang_reqs:
        steps.append(ActionStep(
            order=order,
            title="Assess language requirements",
            description=(
                f"Language expectations for this role and destination: "
                f"{'; '.join(lang_reqs)}."
            ),
            category="preparation",
            estimated_duration="Ongoing",
        ))
        order += 1

    # --- Step: Salary negotiation (if shortfall) ---
    if salary_analysis.threshold_warnings:
        steps.append(ActionStep(
            order=order,
            title="Address salary threshold requirements",
            description=(
                f"Your salary expectation of {salary_analysis.currency_code} "
                f"{salary_analysis.user_expectation:,.0f} falls below one or more "
                f"visa salary thresholds. You must negotiate a salary that meets "
                f"the threshold, or explore alternative visa routes."
            ),
            category="visa",
            estimated_duration="During job search",
        ))
        order += 1

    # --- Step: Job search ---
    market = data.get("market_demand", {})
    steps.append(ActionStep(
        order=order,
        title=f"Begin targeted job search in {data.get('destination_display', request.destination)}",
        description=(
            f"Market demand for {data.get('role_display', request.target_role)} "
            f"is {market.get('level', 'unknown')}. "
            f"Focus on employers with sponsorship capability. "
            f"Target salary range: {salary_analysis.currency_code} "
            f"{salary_analysis.market_min:,.0f}–{salary_analysis.market_max:,.0f}."
        ),
        category="job_search",
        estimated_duration=f"{data['timeline']['typical_hiring_duration_months']['min']}-"
                          f"{data['timeline']['typical_hiring_duration_months']['max']} months",
    ))
    order += 1

    # --- Step: Visa application (for each eligible route) ---
    for route in eligible_routes:
        proc_time = route.processing_time_months
        steps.append(ActionStep(
            order=order,
            title=f"Apply via {route.name}",
            description=(
                f"Route type: {route.type}. "
                f"Sponsorship required: {'Yes' if route.sponsorship_required else 'No'}. "
                f"Processing time: {proc_time.get('min', '?')}-{proc_time.get('max', '?')} months. "
                f"Eligibility criteria: {'; '.join(route.eligibility_criteria)}."
            ),
            category="visa",
            estimated_duration=f"{proc_time.get('min', '?')}-{proc_time.get('max', '?')} months",
        ))
        order += 1

    # --- Step: Timeline adjustment (if conflict) ---
    if not timeline_analysis.is_feasible:
        steps.append(ActionStep(
            order=order,
            title="Adjust your timeline expectations",
            description=(
                f"Your desired timeline of {timeline_analysis.user_timeline_months} months "
                f"is shorter than the minimum realistic estimate of "
                f"{timeline_analysis.estimated_min_months} months. "
                f"Consider extending your timeline to "
                f"{timeline_analysis.estimated_min_months}-"
                f"{timeline_analysis.estimated_max_months} months."
            ),
            category="preparation",
            estimated_duration="Immediate decision",
        ))
        order += 1

    # --- Step: Relocation preparation ---
    steps.append(ActionStep(
        order=order,
        title="Prepare for relocation logistics",
        description=(
            f"Once job offer and visa are secured: arrange housing, "
            f"health insurance, banking, and travel to "
            f"{data.get('destination_display', request.destination)}."
        ),
        category="preparation",
        estimated_duration="2-4 weeks",
    ))

    return steps
