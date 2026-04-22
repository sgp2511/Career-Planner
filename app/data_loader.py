"""
Data loader for destination–role JSON files.

Reads structured data from the file system and validates the expected schema.
Adding a new destination/role requires only adding a new JSON file — no code changes.

Directory structure:
    app/data/{destination_slug}/{role_slug}.json
"""

import json
import os
from pathlib import Path
from typing import Any, Optional

from app.config import get_settings


class DataNotFoundError(Exception):
    """Raised when no data file exists for a destination–role combination."""

    def __init__(self, destination: str, role: str, available: list[dict]):
        self.destination = destination
        self.role = role
        self.available = available
        super().__init__(
            f"No data available for '{role}' in '{destination}'"
        )


class DataValidationError(Exception):
    """Raised when a data file exists but has invalid/missing fields."""

    def __init__(self, path: str, errors: list[str]):
        self.path = path
        self.errors = errors
        super().__init__(
            f"Data validation errors in {path}: {'; '.join(errors)}"
        )


# ---------------------------------------------------------------------------
# Required top-level keys in each destination–role JSON file
# ---------------------------------------------------------------------------
REQUIRED_SECTIONS = [
    "destination",
    "role",
    "salary",
    "work_authorisation",
    "credentials",
    "timeline",
    "market_demand",
]

REQUIRED_SALARY_FIELDS = ["min", "median", "max", "currency_code", "data_confidence"]
REQUIRED_ROUTE_FIELDS = [
    "name",
    "type",
    "sponsorship_required",
    "processing_time_months",
    "eligibility_criteria",
]
REQUIRED_TIMELINE_FIELDS = [
    "typical_hiring_duration_months",
    "visa_processing_months",
    "total_estimated_months",
    "data_confidence",
]


def _get_data_dir() -> Path:
    """Returns the absolute path to the data directory."""
    settings = get_settings()
    # Resolve relative to project root
    data_dir = Path(settings.DATA_DIR)
    if not data_dir.is_absolute():
        data_dir = Path(os.getcwd()) / data_dir
    return data_dir


def _slugify(value: str) -> str:
    """
    Converts a human-readable name to a file-system slug.
    E.g., 'Senior Backend Engineer' -> 'senior_backend_engineer'
          'United Kingdom'          -> 'united_kingdom'
    """
    return value.strip().lower().replace(" ", "_").replace("-", "_")


def _validate_data(data: dict, file_path: str) -> list[str]:
    """
    Validates a loaded data dict against the expected schema.
    Returns a list of error messages (empty if valid).
    """
    errors: list[str] = []

    # Check top-level sections
    for section in REQUIRED_SECTIONS:
        if section not in data:
            errors.append(f"Missing required section: '{section}'")

    if errors:
        return errors  # Can't validate further without top-level sections

    # Validate salary
    salary = data.get("salary", {})
    for field in REQUIRED_SALARY_FIELDS:
        if field not in salary:
            errors.append(f"Missing salary field: '{field}'")

    # Validate work authorisation routes
    wa = data.get("work_authorisation", {})
    routes = wa.get("routes", [])
    if not routes:
        errors.append("work_authorisation.routes must contain at least one route")
    for i, route in enumerate(routes):
        for field in REQUIRED_ROUTE_FIELDS:
            if field not in route:
                errors.append(f"Route [{i}] missing field: '{field}'")

    # Validate timeline
    timeline = data.get("timeline", {})
    for field in REQUIRED_TIMELINE_FIELDS:
        if field not in timeline:
            errors.append(f"Missing timeline field: '{field}'")

    return errors


def load_destination_role_data(destination: str, role: str) -> dict[str, Any]:
    """
    Loads and validates data for a specific destination–role combination.

    Args:
        destination: Country name or slug (e.g., 'Germany' or 'germany')
        role: Role name or slug (e.g., 'Senior Backend Engineer' or 'senior_backend_engineer')

    Returns:
        Validated data dictionary.

    Raises:
        DataNotFoundError: If no matching JSON file exists.
        DataValidationError: If the file exists but is malformed.
    """
    dest_slug = _slugify(destination)
    role_slug = _slugify(role)
    data_dir = _get_data_dir()

    file_path = data_dir / dest_slug / f"{role_slug}.json"

    if not file_path.exists():
        available = get_available_combinations()
        raise DataNotFoundError(destination=dest_slug, role=role_slug, available=available)

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise DataValidationError(
            path=str(file_path),
            errors=[f"Invalid JSON: {str(e)}"],
        )

    # Validate the loaded data
    validation_errors = _validate_data(data, str(file_path))
    if validation_errors:
        raise DataValidationError(path=str(file_path), errors=validation_errors)

    return data


def get_available_combinations() -> list[dict[str, str]]:
    """
    Scans the data directory and returns all available destination–role combinations.
    Useful for the missing-data edge case response.

    Returns:
        List of dicts with 'destination' and 'role' keys.
    """
    data_dir = _get_data_dir()
    combinations: list[dict[str, str]] = []

    if not data_dir.exists():
        return combinations

    for dest_dir in sorted(data_dir.iterdir()):
        if dest_dir.is_dir() and not dest_dir.name.startswith("_"):
            for role_file in sorted(dest_dir.glob("*.json")):
                combinations.append(
                    {
                        "destination": dest_dir.name,
                        "role": role_file.stem,
                    }
                )

    return combinations


def get_data_confidence_summary(data: dict[str, Any]) -> dict[str, str]:
    """
    Extracts and aggregates data_confidence flags from all sections
    of a destination–role data file.

    Returns:
        Dict mapping section name to its confidence level.
        E.g., {"salary": "estimated", "work_authorisation": "verified", ...}
    """
    summary: dict[str, str] = {}

    for section in ["salary", "work_authorisation", "credentials", "timeline", "market_demand"]:
        section_data = data.get(section, {})
        confidence = section_data.get("data_confidence", "unknown")
        summary[section] = confidence

    return summary
