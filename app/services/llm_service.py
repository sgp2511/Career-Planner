"""
LLM service — generates personalised narrative using Groq (Llama 3.3 70B).

CRITICAL BOUNDARY:
- The LLM ONLY generates narrative text (summaries, personalised advice, tone).
- The LLM NEVER decides eligibility, salary thresholds, or timeline feasibility.
- All deterministic results are passed TO the LLM as context — it narrates them.
- If the LLM call fails, the plan is returned WITHOUT a narrative (graceful degradation).

This boundary is documented in DECISIONS.md.
"""

import time
import logging
from typing import Any, Optional

from groq import Groq, APIError, APITimeoutError, RateLimitError

from app.config import get_settings
from app.schemas.plan import PlanResult, PlanRequest

logger = logging.getLogger(__name__)

# Maximum time to wait for the LLM response (seconds)
LLM_TIMEOUT_SECONDS = 15


def _build_prompt(plan: PlanResult, request: PlanRequest) -> str:
    """
    Build a structured prompt for the LLM based on the deterministic plan results.

    The prompt provides the LLM with all factual data and instructs it to
    generate ONLY narrative — never contradict warnings or eligibility decisions.
    """
    # Collect eligible and ineligible routes
    eligible = [v for v in plan.visa_routes if v.is_eligible]
    ineligible = [v for v in plan.visa_routes if not v.is_eligible]

    # Collect warnings text
    warnings_text = ""
    if plan.warnings:
        warnings_text = "\n".join(
            f"  - [{w.severity.upper()}] {w.message}" for w in plan.warnings
        )
    else:
        warnings_text = "  No warnings or conflicts."

    prompt = f"""You are a career relocation advisor. Generate a personalised, honest narrative summary for the following relocation plan.

IMPORTANT RULES:
1. NEVER contradict the warnings or feasibility assessment below. If the feasibility is "not_feasible", say so clearly.
2. NEVER make up eligibility information. Only reference the visa routes listed.
3. Be encouraging where appropriate but ALWAYS be honest about risks and conflicts.
4. Keep the narrative concise (3-5 paragraphs).
5. Address the user directly ("you", "your").

--- USER PROFILE ---
Origin: {request.origin}
Destination: {plan.destination_display}
Target Role: {plan.role_display}
Salary Expectation: {plan.salary_analysis.currency_code} {plan.salary_analysis.user_expectation:,.0f}
Timeline: {request.timeline_months} months
Work Authorisation: {request.work_authorisation_status}

--- DETERMINISTIC ANALYSIS (DO NOT CONTRADICT) ---
Overall Feasibility: {plan.feasibility_score}
Market Demand: {plan.market_demand_level}

Salary Position: {plan.salary_analysis.percentile_estimate}
  Market range: {plan.salary_analysis.currency_code} {plan.salary_analysis.market_min:,.0f} – {plan.salary_analysis.market_max:,.0f}

Timeline Assessment: {"Feasible" if plan.timeline_analysis.is_feasible else "NOT FEASIBLE"}
  Realistic range: {plan.timeline_analysis.estimated_min_months}-{plan.timeline_analysis.estimated_max_months} months

Eligible Visa Routes: {', '.join(r.name for r in eligible) if eligible else 'NONE'}
Ineligible Visa Routes: {', '.join(f"{r.name} (reason: {'; '.join(r.reasons)})" for r in ineligible) if ineligible else 'None'}

Warnings/Conflicts:
{warnings_text}

--- INSTRUCTIONS ---
Write a personalised narrative summary that:
1. Opens with an honest overall assessment of feasibility
2. Highlights the most promising visa route(s) and why
3. Addresses any warnings or conflicts directly and honestly
4. Provides 2-3 practical tips specific to this destination and role
5. Closes with a realistic next-step recommendation

Do NOT use markdown headers. Write in flowing paragraphs."""

    return prompt


def generate_narrative(
    plan: PlanResult,
    request: PlanRequest,
) -> tuple[Optional[str], dict[str, Any]]:
    """
    Call the Groq LLM to generate a personalised narrative for the plan.

    Args:
        plan: The deterministic plan result.
        request: The original user request.

    Returns:
        Tuple of (narrative_text or None, llm_metadata dict).
        If the LLM call fails, narrative_text is None and metadata
        includes the failure reason.
    """
    settings = get_settings()

    llm_metadata: dict[str, Any] = {
        "model": settings.GROQ_MODEL,
        "provider": "groq",
        "latency_ms": None,
        "fallback_used": False,
        "error": None,
    }

    # --- Guard: no API key configured ---
    if not settings.GROQ_API_KEY or settings.GROQ_API_KEY == "your-groq-api-key-here":
        logger.warning("Groq API key not configured — skipping LLM narrative")
        llm_metadata["fallback_used"] = True
        llm_metadata["error"] = "API key not configured"
        return None, llm_metadata

    prompt = _build_prompt(plan, request)

    try:
        client = Groq(
            api_key=settings.GROQ_API_KEY,
            timeout=LLM_TIMEOUT_SECONDS,
        )

        start_time = time.time()

        completion = client.chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a professional career relocation advisor. "
                        "You provide honest, personalised advice based on factual data. "
                        "You never make up information or contradict the analysis provided."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
            max_tokens=1024,
        )

        elapsed_ms = int((time.time() - start_time) * 1000)
        llm_metadata["latency_ms"] = elapsed_ms

        narrative = completion.choices[0].message.content
        logger.info(f"LLM narrative generated in {elapsed_ms}ms")

        return narrative, llm_metadata

    except APITimeoutError:
        logger.warning("Groq API timed out — returning plan without narrative")
        llm_metadata["fallback_used"] = True
        llm_metadata["error"] = f"API timeout ({LLM_TIMEOUT_SECONDS}s)"
        return None, llm_metadata

    except RateLimitError as e:
        logger.warning(f"Groq rate limit hit: {e}")
        llm_metadata["fallback_used"] = True
        llm_metadata["error"] = "Rate limit exceeded"
        return None, llm_metadata

    except APIError as e:
        logger.error(f"Groq API error: {e}")
        llm_metadata["fallback_used"] = True
        llm_metadata["error"] = f"API error: {str(e)}"
        return None, llm_metadata

    except Exception as e:
        logger.error(f"Unexpected LLM error: {e}")
        llm_metadata["fallback_used"] = True
        llm_metadata["error"] = f"Unexpected: {str(e)}"
        return None, llm_metadata
