"""
Pydantic schemas for plan generation requests and responses.

These schemas define the API contract — designed so a mobile team
can consume the same endpoints.
"""

from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional


# ---------------------------------------------------------------------------
# Request
# ---------------------------------------------------------------------------
class PlanRequest(BaseModel):
    """Input for generating a relocation plan."""

    origin: str = Field(
        ..., description="Country of origin", examples=["India"]
    )
    destination: str = Field(
        ..., description="Target destination country", examples=["Germany"]
    )
    target_role: str = Field(
        ..., description="Desired job role", examples=["Senior Backend Engineer"]
    )
    salary_expectation: float = Field(
        ..., gt=0, description="Expected salary in destination currency", examples=[45000]
    )
    timeline_months: int = Field(
        ..., gt=0, le=120, description="Desired timeline in months", examples=[12]
    )
    work_authorisation_status: str = Field(
        ...,
        description="Current work authorisation status",
        examples=["needs_sponsorship", "no_constraint"],
    )


# ---------------------------------------------------------------------------
# Warning / conflict sub-schemas
# ---------------------------------------------------------------------------
class PlanWarning(BaseModel):
    """A warning or conflict identified during plan analysis."""

    category: str = Field(
        ..., description="Warning category",
        examples=["timeline_conflict", "salary_shortfall", "eligibility"]
    )
    severity: str = Field(
        ..., description="Severity level: info | warning | critical"
    )
    message: str = Field(
        ..., description="Human-readable warning message"
    )


# ---------------------------------------------------------------------------
# Sub-sections of the plan response
# ---------------------------------------------------------------------------
class SalaryAnalysis(BaseModel):
    """Deterministic salary comparison result."""

    user_expectation: float
    currency_code: str
    market_min: float
    market_median: float
    market_max: float
    is_within_market_range: bool
    percentile_estimate: str = Field(
        ..., description="Where the user's expectation sits relative to market"
    )
    threshold_warnings: list[PlanWarning] = Field(
        default_factory=list,
        description="Warnings about visa salary thresholds",
    )


class TimelineAnalysis(BaseModel):
    """Deterministic timeline feasibility result."""

    user_timeline_months: int
    estimated_min_months: int
    estimated_max_months: int
    is_feasible: bool
    warnings: list[PlanWarning] = Field(default_factory=list)


class VisaRouteAssessment(BaseModel):
    """Assessment of a single visa route for the user."""

    name: str
    type: str
    is_eligible: bool
    sponsorship_required: bool
    processing_time_months: dict = Field(
        ..., description="{'min': X, 'max': Y}"
    )
    salary_threshold: float | None = None
    meets_salary_threshold: bool | None = None
    eligibility_criteria: list[str]
    reasons: list[str] = Field(
        default_factory=list,
        description="Reasons for eligibility/ineligibility",
    )
    data_confidence: str


class ActionStep(BaseModel):
    """A single step in the ranked action plan."""

    order: int
    title: str
    description: str
    category: str = Field(
        ..., description="e.g. 'job_search', 'visa', 'credentials', 'preparation'"
    )
    estimated_duration: str | None = None


class DataConfidenceSummary(BaseModel):
    """Per-section data confidence levels."""

    salary: str
    work_authorisation: str
    credentials: str
    timeline: str
    market_demand: str


class LlmMetadata(BaseModel):
    """Metadata about the LLM call for transparency."""

    model: str | None = None
    provider: str | None = None
    latency_ms: int | None = None
    fallback_used: bool = False
    error: str | None = None


# ---------------------------------------------------------------------------
# Top-level plan response
# ---------------------------------------------------------------------------
class PlanResult(BaseModel):
    """The full generated relocation plan — returned by the plan engine."""

    destination: str
    destination_display: str
    role: str
    role_display: str
    feasibility_score: str = Field(
        ..., description="Overall feasibility: high | medium | low | not_feasible"
    )
    salary_analysis: SalaryAnalysis
    timeline_analysis: TimelineAnalysis
    visa_routes: list[VisaRouteAssessment]
    action_steps: list[ActionStep]
    warnings: list[PlanWarning]
    data_confidence: DataConfidenceSummary
    market_demand_level: str
    narrative: str | None = Field(
        None, description="LLM-generated personalised narrative summary"
    )
    llm_metadata: LlmMetadata | None = Field(
        None, description="Metadata about the LLM call (model, latency, fallback)"
    )


class GeneratePlanResponse(BaseModel):
    """API response wrapper for plan generation."""

    plan: PlanResult
    input_summary: PlanRequest
    generated_at: datetime


# ---------------------------------------------------------------------------
# Saved plan schemas
# ---------------------------------------------------------------------------
class SavePlanRequest(BaseModel):
    """Request to save a generated plan."""

    plan: PlanResult
    input_summary: PlanRequest
    title: str | None = Field(
        None, description="Optional custom title; auto-generated if omitted"
    )


class SavedPlanSummary(BaseModel):
    """Summary of a saved plan for list views."""

    id: int
    title: str
    destination: str
    role: str
    created_at: datetime

    model_config = {"from_attributes": True}


class SavedPlanDetail(BaseModel):
    """Full saved plan detail."""

    id: int
    title: str
    input_snapshot: dict
    result: dict
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Error response for missing data
# ---------------------------------------------------------------------------
class DataNotAvailableResponse(BaseModel):
    """Structured response when destination/role data is not available."""

    error: str = "data_not_available"
    message: str
    available_combinations: list[dict[str, str]]
