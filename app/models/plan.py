"""
Plan ORM model.

Stores user-generated relocation plans with full input snapshot and result.
"""

from datetime import datetime, timezone

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship

from app.database import Base


class Plan(Base):
    """A saved relocation plan belonging to a user."""

    __tablename__ = "plans"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # Store the exact input the user provided — useful for audit & re-generation
    input_snapshot = Column(JSON, nullable=False)

    # Store the full generated plan result
    result = Column(JSON, nullable=False)

    # Human-readable title for the plan list view
    title = Column(String(500), nullable=False)

    created_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    # Relationship back to user
    user = relationship("User", back_populates="plans")

    def __repr__(self) -> str:
        return f"<Plan id={self.id} user_id={self.user_id} title={self.title}>"
