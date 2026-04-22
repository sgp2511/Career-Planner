"""
Plans router — generate, save, list, and retrieve relocation plans.

All endpoints require JWT authentication.
All endpoints prefixed with /api/v1/plans.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth.jwt import get_current_user
from app.models.user import User
from app.models.plan import Plan
from app.data_loader import DataNotFoundError
from app.services.plan_engine import generate_plan
from app.schemas.plan import (
    PlanRequest,
    GeneratePlanResponse,
    SavePlanRequest,
    SavedPlanSummary,
    SavedPlanDetail,
    DataNotAvailableResponse,
)

router = APIRouter(prefix="/api/v1/plans", tags=["Plans"])


# ---------------------------------------------------------------------------
# POST /api/v1/plans/generate
# ---------------------------------------------------------------------------
@router.post(
    "/generate",
    response_model=GeneratePlanResponse,
    summary="Generate a relocation plan",
    responses={
        404: {
            "model": DataNotAvailableResponse,
            "description": "Destination/role data not available",
        }
    },
)
def generate(
    request: PlanRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Generate a personalised relocation plan based on the user's profile.

    The plan includes:
    - Visa route eligibility assessment (deterministic)
    - Salary analysis against market data (deterministic)
    - Timeline feasibility check (deterministic)
    - Ranked action steps
    - Data confidence summary
    - Warnings for any conflicts or shortfalls

    Requires authentication.
    """
    try:
        plan_result = generate_plan(request)
    except DataNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "data_not_available",
                "message": str(e),
                "available_combinations": e.available,
            },
        )

    return GeneratePlanResponse(
        plan=plan_result,
        input_summary=request,
        generated_at=datetime.now(timezone.utc),
    )


# ---------------------------------------------------------------------------
# POST /api/v1/plans/save
# ---------------------------------------------------------------------------
@router.post(
    "/save",
    response_model=SavedPlanSummary,
    status_code=status.HTTP_201_CREATED,
    summary="Save a generated plan",
)
def save_plan(
    request: SavePlanRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Save a previously generated plan to the user's account.

    The full plan result and input are persisted as JSON so the user
    can return to it in a future session.
    """
    # Auto-generate title if not provided
    title = request.title or (
        f"{request.plan.role_display} in {request.plan.destination_display}"
    )

    plan = Plan(
        user_id=current_user.id,
        title=title,
        input_snapshot=request.input_summary.model_dump(),
        result=request.plan.model_dump(),
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)

    return SavedPlanSummary(
        id=plan.id,
        title=plan.title,
        destination=request.plan.destination_display,
        role=request.plan.role_display,
        created_at=plan.created_at,
    )


# ---------------------------------------------------------------------------
# GET /api/v1/plans
# ---------------------------------------------------------------------------
@router.get(
    "",
    response_model=list[SavedPlanSummary],
    summary="List saved plans",
)
def list_plans(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Returns all saved plans for the authenticated user,
    ordered by most recently created first.
    """
    plans = (
        db.query(Plan)
        .filter(Plan.user_id == current_user.id)
        .order_by(Plan.created_at.desc())
        .all()
    )

    summaries = []
    for p in plans:
        result_data = p.result or {}
        summaries.append(
            SavedPlanSummary(
                id=p.id,
                title=p.title,
                destination=result_data.get("destination_display", "Unknown"),
                role=result_data.get("role_display", "Unknown"),
                created_at=p.created_at,
            )
        )
    return summaries


# ---------------------------------------------------------------------------
# GET /api/v1/plans/{plan_id}
# ---------------------------------------------------------------------------
@router.get(
    "/{plan_id}",
    response_model=SavedPlanDetail,
    summary="Get a saved plan by ID",
)
def get_plan(
    plan_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Retrieve a specific saved plan by ID.

    Users can only access their own plans.
    """
    plan = (
        db.query(Plan)
        .filter(Plan.id == plan_id, Plan.user_id == current_user.id)
        .first()
    )
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Plan not found or access denied",
        )

    return SavedPlanDetail(
        id=plan.id,
        title=plan.title,
        input_snapshot=plan.input_snapshot,
        result=plan.result,
        created_at=plan.created_at,
    )
