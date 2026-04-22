"""
Deterministic salary analysis service.

Compares user's salary expectation against market data.
Checks visa salary thresholds.

This is DETERMINISTIC — results are factual comparisons, never LLM-generated.
"""

from typing import Any

from app.schemas.plan import SalaryAnalysis, PlanWarning


def analyse_salary(
    salary_data: dict[str, Any],
    salary_expectation: float,
    visa_routes: list[dict[str, Any]],
) -> SalaryAnalysis:
    """
    Compare user's salary expectation against market data and visa thresholds.

    Args:
        salary_data: Market salary data from the data layer.
        salary_expectation: User's expected salary.
        visa_routes: Visa route data (for threshold checks).

    Returns:
        SalaryAnalysis with market comparison and threshold warnings.
    """
    market_min = salary_data["min"]
    market_median = salary_data["median"]
    market_max = salary_data["max"]
    currency = salary_data["currency_code"]

    # --- Market range check ---
    is_within_range = market_min <= salary_expectation <= market_max

    # --- Percentile estimate ---
    if salary_expectation < market_min:
        percentile = "Below market minimum"
    elif salary_expectation <= market_median:
        # Linear interpolation between min and median (0-50th percentile)
        if market_median > market_min:
            pct = ((salary_expectation - market_min) / (market_median - market_min)) * 50
        else:
            pct = 25
        percentile = f"Approximately {pct:.0f}th percentile (below median)"
    elif salary_expectation <= market_max:
        # Linear interpolation between median and max (50-100th percentile)
        if market_max > market_median:
            pct = 50 + ((salary_expectation - market_median) / (market_max - market_median)) * 50
        else:
            pct = 75
        percentile = f"Approximately {pct:.0f}th percentile (above median)"
    else:
        percentile = "Above market maximum"

    # --- Visa salary threshold warnings ---
    threshold_warnings: list[PlanWarning] = []
    for route in visa_routes:
        threshold = route.get("salary_threshold")
        if threshold is not None and salary_expectation < threshold:
            shortfall = threshold - salary_expectation
            threshold_warnings.append(
                PlanWarning(
                    category="salary_shortfall",
                    severity="critical",
                    message=(
                        f"Your salary expectation of {currency} {salary_expectation:,.0f} "
                        f"is {currency} {shortfall:,.0f} below the {route['name']} "
                        f"minimum threshold of {currency} {threshold:,.0f}. "
                        f"You will NOT be eligible for this route at this salary."
                    ),
                )
            )

    return SalaryAnalysis(
        user_expectation=salary_expectation,
        currency_code=currency,
        market_min=market_min,
        market_median=market_median,
        market_max=market_max,
        is_within_market_range=is_within_range,
        percentile_estimate=percentile,
        threshold_warnings=threshold_warnings,
    )
