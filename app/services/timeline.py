"""
Deterministic timeline analysis service.

Compares user's desired timeline against realistic estimates
(hiring duration + visa processing).

This is DETERMINISTIC — timeline conflicts are factual, never softened by an LLM.
"""

from typing import Any

from app.schemas.plan import TimelineAnalysis, PlanWarning


def analyse_timeline(
    timeline_data: dict[str, Any],
    user_timeline_months: int,
    eligible_routes: list[dict] | None = None,
) -> TimelineAnalysis:
    """
    Check whether the user's desired timeline is feasible.

    Args:
        timeline_data: Timeline estimates from the data layer.
        user_timeline_months: User's desired timeline in months.
        eligible_routes: Optional list of eligible visa routes (for
            route-specific processing times).

    Returns:
        TimelineAnalysis with feasibility assessment and warnings.
    """
    hiring_min = timeline_data["typical_hiring_duration_months"]["min"]
    hiring_max = timeline_data["typical_hiring_duration_months"]["max"]
    visa_min = timeline_data["visa_processing_months"]["min"]
    visa_max = timeline_data["visa_processing_months"]["max"]

    total_min = hiring_min + visa_min
    total_max = hiring_max + visa_max

    is_feasible = user_timeline_months >= total_min
    warnings: list[PlanWarning] = []

    # --- Critical conflict: user timeline < minimum possible ---
    if user_timeline_months < total_min:
        warnings.append(
            PlanWarning(
                category="timeline_conflict",
                severity="critical",
                message=(
                    f"Your desired timeline of {user_timeline_months} month(s) "
                    f"conflicts with the minimum realistic estimate of {total_min} months "
                    f"(hiring: {hiring_min}-{hiring_max} months + visa processing: "
                    f"{visa_min}-{visa_max} months). "
                    f"The earliest realistic start is {total_min}-{total_max} months. "
                    f"This is NOT an optimistic estimate — it is a hard constraint."
                ),
            )
        )

    # --- Warning: user timeline is tight (between min and max) ---
    elif user_timeline_months < total_max:
        warnings.append(
            PlanWarning(
                category="timeline_conflict",
                severity="warning",
                message=(
                    f"Your timeline of {user_timeline_months} months is possible "
                    f"but tight. The realistic range is {total_min}-{total_max} months. "
                    f"Delays in hiring or visa processing could push beyond your deadline."
                ),
            )
        )

    # --- Route-specific timeline warnings ---
    if eligible_routes:
        for route in eligible_routes:
            proc_time = route.get("processing_time_months", {})
            route_min = proc_time.get("min", 0)
            route_max = proc_time.get("max", 0)

            # If visa processing alone exceeds user's timeline
            if user_timeline_months < route_min:
                warnings.append(
                    PlanWarning(
                        category="timeline_conflict",
                        severity="critical",
                        message=(
                            f"The {route.get('name', 'visa route')} alone requires "
                            f"{route_min}-{route_max} months for processing. "
                            f"Your timeline of {user_timeline_months} month(s) "
                            f"is insufficient for this route."
                        ),
                    )
                )

    return TimelineAnalysis(
        user_timeline_months=user_timeline_months,
        estimated_min_months=total_min,
        estimated_max_months=total_max,
        is_feasible=is_feasible,
        warnings=warnings,
    )
