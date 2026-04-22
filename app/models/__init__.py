"""
Models package — import all models so Base.metadata.create_all() discovers them.
"""

from app.models.user import User
from app.models.plan import Plan

__all__ = ["User", "Plan"]
